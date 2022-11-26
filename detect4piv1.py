import argparse
import time
from pathlib import Path

import cv2
import torch
import torch.backends.cudnn as cudnn
from numpy import random
import numpy as np
from utils.datasets import LoadStreams, LoadImages
from utils.general import check_img_size, non_max_suppression, apply_classifier, scale_coords, xyxy2xywh, \
    strip_optimizer, set_logging, increment_path
from utils.plots import plot_one_box
from utils.torch_utils import select_device, load_classifier, time_synchronized
import importlib.util


def detect(save_img=False):
    source, weights, view_img, save_txt, imgsz = opt.source, opt.weights, opt.view_img, opt.save_txt, opt.img_size
    webcam = source.isnumeric() or source.endswith('.txt') or source.lower().startswith(
        ('rtsp://', 'rtmp://', 'http://'))

    # Directories
    save_dir = Path(increment_path(Path(opt.project) / opt.name, exist_ok=opt.exist_ok))  # increment run
    (save_dir / 'labels' if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    if len(imgsz) == 1:
        imgsz = imgsz[0]

    # Initialize
    set_logging()
    device = select_device(opt.device)
    half = device.type != 'cpu'  # half precision only supported on CUDA

    # Load model
    if weights.split('.')[-1] == 'pt':
        backend = 'pytorch'
    elif weights.split('.')[-1] == 'pb':
        backend = 'graph_def'
    elif weights.split('.')[-1] == 'tflite':
        backend = 'tflite'
    else:
        backend = 'tflite'

    if backend=='tflite':
        pkg = importlib.util.find_spec('tflite_runtime')
        if pkg:
            from tflite_runtime.interpreter import Interpreter
            if use_TPU:
                from tflite_runtime.interpreter import load_delegate
        else:
            from tensorflow.lite.python.interpreter import Interpreter
            if use_TPU:
                from tensorflow.lite.python.interpreter import load_delegate

    if backend == 'tflite':
        # Load TFLite model and allocate tensors.
        if use_TPU:
            interpreter = Interpreter(model_path=opt.weights[0],
                              experimental_delegates=[load_delegate('libedgetpu.so.1.0')])
            print(opt.weights[0])
        else:
            print(opt.weights)
            interpreter = Interpreter(model_path=opt.weights)
        interpreter.allocate_tensors()

        # Get input and output tensors.
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

    # Set Dataloader
    vid_path, vid_writer = None, None
    if webcam:
        view_img = True
        #cudnn.benchmark = True  # set True to speed up constant image size inference
        dataset = LoadStreams(source, img_size=imgsz)
    else:
        save_img = True
        dataset = LoadImages(source, img_size=imgsz, auto=False)

    # Get names and colors
    names =['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

    # Run inference
    t0 = time.time()
    if isinstance(imgsz, int):
        imgsz = (imgsz, imgsz)
    img = torch.zeros((1, 3, *imgsz), device=device)  # init img

    if backend == 'tflite':
        input_data = img.permute(0, 1, 2, 3).cpu().numpy()
        if opt.tfl_int8:
            input_data = input_data.astype(np.uint8)
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])

    for path, img, im0s, vid_cap in dataset:
        img= np.resize(img,(1,3,imgsz[0],imgsz[0]))
        img = torch.from_numpy(img).to(device)
        img = img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Inference
        t1 = time_synchronized()

        if backend == 'tflite':
            input_data = img.permute(0, 1, 2, 3).cpu().numpy()
            if opt.tfl_int8:
                scale, zero_point = input_details[0]['quantization']
                input_data = input_data / scale + zero_point
                input_data = input_data.astype(np.uint8)
            interpreter.set_tensor(input_details[0]['index'], input_data)
            interpreter.invoke()
            if not opt.tfl_detect:
                output_data = interpreter.get_tensor(output_details[0]['index'])
                pred = torch.tensor(output_data)
            else:
                import yaml
                yaml_file = Path(opt.cfg).name
                with open(opt.cfg) as f:
                    yaml = yaml.load(f, Loader=yaml.FullLoader)

                anchors = yaml['anchors']
                nc = yaml['nc']
                nl = len(anchors)
                x = [torch.tensor(interpreter.get_tensor(output_details[i]['index']), device=device) for i in range(nl)]
                if opt.tfl_int8:
                    for i in range(nl):
                        scale, zero_point = output_details[i]['quantization']
                        x[i] = x[i].float()
                        x[i] = (x[i] - zero_point) * scale

                def _make_grid(nx=20, ny=20):
                    yv, xv = torch.meshgrid([torch.arange(ny), torch.arange(nx)])
                    return torch.stack((xv, yv), 2).view((1, 1, ny * nx, 2)).float()

                no = nc + 5
                grid = [torch.zeros(1)] * nl  # init grid
                a = torch.tensor(anchors).float().view(nl, -1, 2).to(device)
                anchor_grid = a.clone().view(nl, 1, -1, 1, 2)  # shape(nl,1,na,1,2)
                z = []  # inference output
                for i in range(nl):
                    _, _, ny_nx,_, _ = x[i].shape
                    r = imgsz[0] / imgsz[1]
                    nx = int(np.sqrt(ny_nx / r))
                    ny = int(r * nx)
                    grid[i] = _make_grid(nx, ny).to(x[i].device)
                    stride = imgsz[0] // ny
                    y = x[i].sigmoid()
                    y[..., 0:2] = (y[..., 0:2] * 2. - 0.5 + grid[i].to(x[i].device)) * stride  # xy
                    y[..., 2:4] = (y[..., 2:4] * 2) ** 2 * anchor_grid[i]  # wh
                    z.append(y.view(-1, no))

                pred = torch.unsqueeze(torch.cat(z, 0), 0)

        # Apply NMS
        if not opt.no_tf_nms:
            pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres, classes=opt.classes, agnostic=opt.agnostic_nms)
        else:
            nmsed_boxes, nmsed_scores, nmsed_classes, valid_detections = pred
            if not tf.__version__.startswith('1'):
                nmsed_boxes = torch.tensor(nmsed_boxes.numpy())
                nmsed_scores = torch.tensor(nmsed_scores.numpy())
                nmsed_classes = torch.tensor(nmsed_classes.numpy())
                valid_detections = torch.tensor(valid_detections.numpy())
            else:
                nmsed_boxes = torch.tensor(nmsed_boxes)
                nmsed_scores = torch.tensor(nmsed_scores)
                nmsed_classes = torch.tensor(nmsed_classes)
                valid_detections = torch.tensor(valid_detections)
            bs = nmsed_boxes.shape[0]
            pred = [None] * bs
            for i in range(bs):
                pred[i] = torch.cat([nmsed_boxes[i, :valid_detections[i], :],
                                     torch.unsqueeze(nmsed_scores[i, :valid_detections[i]], -1),
                                     torch.unsqueeze(nmsed_classes[i, :valid_detections[i]], -1)], -1)

        t2 = time_synchronized()

        # Process detections
        for i, det in enumerate(pred):  # detections per image
            if webcam:  # batch_size >= 1
                p, s, im0 = Path(path[i]), '%g: ' % i, im0s[i].copy()
            else:
                p, s, im0 = Path(path), '', im0s

            save_path = str(save_dir / p.name)
            txt_path = str(save_dir / 'labels' / p.stem) + ('_%g' % dataset.frame if dataset.mode == 'video' else '')
            s += '%gx%g ' % img.shape[2:]  # print string
            gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
            if det is not None and len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

                # Print results
                for c in det[:, -1].unique():
                    n = (det[:, -1] == c).sum()  # detections per class
                    s += '%g %ss, ' % (n, names[int(c)])  # add to string

                # Write results
                for *xyxy, conf, cls in reversed(det):
                    if save_txt:  # Write to file
                        xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                        line = (cls, *xywh, conf) if opt.save_conf else (cls, *xywh)  # label format
                        with open(txt_path + '.txt', 'a') as f:
                            f.write(('%g ' * len(line)).rstrip() % line + '\n')

                    if save_img or view_img:  # Add bbox to image
                        label = '%s %.2f' % (names[int(cls)], conf)
                        plot_one_box(xyxy, im0, label=label, color=colors[int(cls)], line_thickness=3)

            # Print time (inference + NMS)
            print('%sDone. (%.3fs)' % (s, t2 - t1))

            # Stream results
            if view_img:
                cv2.imshow(str(p), im0)
                if cv2.waitKey(1) == ord('q'):  # q to quit
                    raise StopIteration

            # Save results (image with detections)
            if save_img:
                if dataset.mode == 'images':
                    cv2.imwrite(save_path, im0)
                else:
                    if vid_path != save_path:  # new video
                        vid_path = save_path
                        if isinstance(vid_writer, cv2.VideoWriter):
                            vid_writer.release()  # release previous video writer

                        fourcc = 'mp4v'  # output video codec
                        fps = vid_cap.get(cv2.CAP_PROP_FPS)
                        w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*fourcc), fps, (w, h))
                    vid_writer.write(im0)

    print('Done. (%.3fs)' % (time.time() - t0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default='model_ASL.tflite', help='model.pt path(s)')
    parser.add_argument('--source', type=str, default= '2', help='source')  # file/folder, 0 for webcam
    parser.add_argument('--img-size', nargs='+', type=int, default=[416], help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IOU threshold for NMS')
    parser.add_argument('--device', default='cpu', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='display results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --class 0, or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default='runs/detect', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--tfl-detect', default=True, action='store_true', help='add Detect module in TFLite')
    parser.add_argument('--cfg', type=str, default='./models/yolov5s_ASL.yaml', help='cfg path')
    parser.add_argument('--tfl-int8', default=False, action='store_true', help='use int8 quantized TFLite model')
    parser.add_argument('--no-tf-nms', action='store_true', help='dont proceed NMS due to model w/ TensorFlow NMS')
    parser.add_argument('--edgetpu', help='Use Coral Edge TPU Accelerator to speed up detection',action='store_true')
    opt = parser.parse_args()
    print(opt)
    use_TPU = opt.edgetpu

    detect()


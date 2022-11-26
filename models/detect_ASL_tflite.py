#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 25 18:16:00 2022

@author: ec-work2
"""

import tensorflow.lite as tfl
import io
import time
import cv2
import numpy as np
from timeit import default_timer as timer

#LOGGER.info(f'Loading {w} for TensorFlow Lite inference...')
interpreter = tfl.Interpreter(model_path="./ASL_1000epochs_416_16-fp16.tflite")  # load TFLite model
interpreter.allocate_tensors()  # allocate
input_details = interpreter.get_input_details()  # inputs
output_details = interpreter.get_output_details()  # outputs
_,height,width,_ = input_details[0]['shape']
print(height, width)

floating_model = False
if input_details[0]['dtype'] == np.float32:
    floating_model = True

cap=cv2.VideoCapture(1)

ret,image=cap.read()
image=cv2.imresize(image,(width,height))
image=np.expand_dims(image,axis=0)


if floating_model:
    image = np.array(image, dtype=np.float32) / 255.0

# Test model on image.
interpreter.set_tensor(input_details[0]['index'], image)
start = timer()
interpreter.invoke()
end = timer()
print('Elapsed time is ', (end-start)*1000, 'ms')

# The function `get_tensor()` returns a copy of the tensor data.
# Use `tensor()` in order to get a pointer to the tensor.
output_data = interpreter.get_tensor(output_details[0]['index'])
print(output_data)
j = np.argmax(output_data)
# if j == 0:
#     print("Non-Fire")
# else:
#     print("Fire")

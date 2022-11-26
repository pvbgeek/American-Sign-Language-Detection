#!/bin/bash

declare -a threshold=(0.5 0.55 0.6 0.65 0.7 0.75 0.8 0.85 0.9 0.95)
declare -a imgsz=(64 128 160 320 640)
declare -a weight=("ASL_64_16_nano.pt" "ASL_128_16_nano.pt" "ASL_160_16_nano.pt" "ASL_320_16_nano.pt")

printf "Enter Path of YoloV5:\n"
read yolo

printf "Enter Path of Detect.py:\n"
read v5path

printf "Enter Path of Dataset1:\n"
read datapath1

printf "Enter Path of Dataset2:\n"
read datapath2

for z in "${threshold[@]}"
do
	for i in "${imgsz[@]}"
	do
		for j in "${weight[@]}"
		do
			eval "python3 '$v5path' --weights '$yolo/$j' --source '$datapath1/' --imgsz=$i --conf-thres=$z"
			eval "python3 '$v5path' --weights '$yolo/$j' --source '$datapath2/' --imgsz=$i --conf-thres=$z"
		done
	done
done

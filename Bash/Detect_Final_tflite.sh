#!/bin/bash

declare -a threshold=(0.5 0.55 0.6 0.65 0.7 0.75 0.8 0.85 0.9 0.95)
declare -a imgsz=(64 128 192 256 320)
declare -a weight=(64 128 192 256 320)
und="_"
fp="fp16"
ext=".tflite"
model="Tflitefp_16_best"

printf "Enter Path of Best Models:\n"
read tfpath

printf "Enter Path of Detect.py:\n"
read v5path

printf "Enter Path of Dataset1:\n"
read datapath1

printf "Enter Path of Dataset2:\n"
read datapath2

for ((k=0;k<=1;k++))
do
	for z in "${threshold[@]}"
	do
		for i in "${weight[@]}"
		do
			for j in "${imgsz[@]}"
			do
				eval "python3.7 '$v5path' --weights '$tfpath/$model/$i$und$j$und$fp$ext' --source '$datapath1/' --data ./ASL-1.yaml --imgsz=$j --conf-thres=$z"
				eval "python3.7 '$v5path' --weights '$tfpath/$model/$i$und$j$und$fp$ext' --source '$datapath2/' --data ./ASL-2.yaml --imgsz=$j --conf-thres=$z"
			done
		done
	done
	fp="int8"
	model="Tfliteint8_16_best"
done


#!/bin/bash

write_csv(){
	echo $1,$2,$3,$4,$5,$6,$7 >> log.csv
}

read_txt(){
	INPUT=$1
	f1=0
	precision=0
	OLDIFS=$IFS
	IFS=','
	[ ! -f $INPUT ] && { echo "$INPUT file not found"; exit 99; }
	while read f1 precision
	do
		echo "F1: $f1"
		echo "Precision: $precision"
		IFS=$OLDIFS
		write_csv $2,$3,$4,$5,$6,$f1,$precision
	done < $INPUT

}

declare -a threshold=(0.5 0.55 0.6 0.65 0.7 0.75 0.8 0.85 0.9 0.95)
declare -a imgsz=(64 128 160 320 640)
declare -a weight=("ASL_64_16_nano.pt" "ASL_128_16_nano.pt" "ASL_160_16_nano.pt" "ASL_320_16_nano.pt")
declare -a res_val=()

echo "Dataset","Weights","Image Size","Threshold","FileName","F1_Value","Precision_Value" >> log.csv

printf "Enter Python Version:\n"
read py_ver

if [[ $py_ver -ne 0 ]]
then
	py_ver='python3.7'
else
	py_ver='python3'
fi

echo "Python Version: $py_ver"

printf "Enter Path of YoloV5: \n"
read yolo

tout=1

for z in "${threshold[@]}"
do
	for i in "${imgsz[@]}"
	do
		for j in "${weight[@]}"
		do
			file='exp'
			if [[ $tout -ne 1 ]]
			then
				file+=$tout
			fi
			tout=$((tout+1))
			eval "$py_ver '$yolo/val.py' --imgsz $i --batch-size 1 --task test --data '$yolo/data/ASL-1.yaml' --weights '$yolo/$j' --save-hybrid --conf-thres $z"
			file_path="$yolo/runs/val/$file/Results.csv"
			read_txt "$file_path" 1 "$j" "$i" "$z" "$file"
			file='exp'
			if [[ $tout -ne 1 ]]
			then
				file+=$tout
			fi
			eval "$py_ver '$yolo/val.py' --imgsz $i --batch-size 1 --task test --data '$yolo/data/ASL-2.yaml' --weights '$yolo/$j' --save-hybrid --conf-thres $z"
			file_path="$yolo/runs/val/$file/Results.csv"
			read_txt "$file_path" 2 "$j" "$i" "$z" "$file"
			tout=$((tout+1))
		done
	done
done

#!/bin/bash

write_csv(){
	echo $1,$2,$3,$4,$5,$6,$7 >> intel_tf_fp.csv
}

write_csv_int8(){
	echo $1,$2,$3,$4,$5,$6,$7 >> intel_tf_int8.csv
}

read_txt(){
	INPUT=$1
	f1=0
	precision=0
	OLDIFS=$IFS
	fp_file=intel_tf_fp.csv
	int8_file=intel_tf_int8.csv
	IFS=','
	[ ! -f $INPUT ] && { echo "$INPUT file not found"; exit 99; }
	while read f1 precision
	do
		echo "F1: $f1"
		echo "Precision: $precision"
		IFS=$OLDIFS
		if [[ $7 -eq 0 ]]
		then
			write_csv $2,$3,$4,$5,$6,$f1,$precision
		else
			write_csv_int8 $2,$3,$4,$5,$6,$f1,$precision
		fi
	done < $INPUT

}

declare -a threshold=(0.5 0.55 0.6 0.65 0.7 0.75 0.8 0.85 0.9 0.95)
declare -a imgsz=(64 128 192 256 320)
declare -a weight=(64 128 192 256 320)
declare -a res_val=()

echo "Dataset","Weights","Image Size","Threshold","FileName","F1_Value","Precision_Value" >> intel_tf_fp.csv
echo "Dataset","Weights","Image Size","Threshold","FileName","F1_Value","Precision_Value" >> intel_tf_int8.csv

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

printf "Enter Path of Best Model\n"
read bestPath

model="Tflitefp_16_best"

fp="fp16"
und="_"

tout=401

dSet=0

for ((k=0;k<2;k++))
do
	for z in "${threshold[@]}"
	do
		for j in "${weight[@]}"
		do
			for i in "${imgsz[@]}"
			do
				file='exp'
				if [[ $tout -ne 1 ]]
				then
					file+=$tout
				fi
				tout=$((tout+1))
				eval "$py_ver '$yolo/val.py' --imgsz $i --batch-size 16 --task test --data '$yolo/data/ASL-1.yaml' --weights '$bestPath/$model/$j$und$i$und$fp.tflite' --save-hybrid --conf-thres $z"
				file_path="$yolo/runs/val/$file/Results.csv"
				read_txt "$file_path" 1 "$j" "$i" "$z" "$file" "$dSet"
				file='exp'
				if [[ $tout -ne 1 ]]
				then
					file+=$tout
				fi
				eval "$py_ver '$yolo/val.py' --imgsz $i --batch-size 16 --task test --data '$yolo/data/ASL-2.yaml' --weights '$bestPath/$model/$j$und$i$und$fp.tflite' --save-hybrid --conf-thres $z"
				file_path="$yolo/runs/val/$file/Results.csv"
				read_txt "$file_path" 2 "$j" "$i" "$z" "$file" "$dSet"
				tout=$((tout+1))
			done
		done
	done
	fp="int8"
	model="Tfliteint8_16_best"
	dSet=1
done

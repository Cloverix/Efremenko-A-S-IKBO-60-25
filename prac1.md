## Задача 2
cat protocols | awk '{print $2, $1}' | sort -r | tail -5

## Задача 2
`cat protocols | awk '{print $2, $1}' | sort -r | tail -5`

## Задача 3
Код bash:

```
#!/usr/bin/bash

str=$1
len=$(( ${#str} + 4 ))
for (( i = 0; i < len; i++ )); do
        if (( i == 0 || i == len - 1 )); then
                echo -n +
        else
                echo -n -
        fi
done
printf '\n| %s |\n' "$str"
for (( i = 0; i < len; i++ )); do
        if (( i == 0 || i == len - 1 )); then
                echo -n +
        else
                echo -n -
        fi
done
printf '\n'
```

Работа скрипта:
```
cloverix@cloverix-MDG-XX:~/test$ ./banner "Hello from RTU MIREA!"
+-----------------------+
| Hello from RTU MIREA! |
+-----------------------+
```

## Задача 4
код bash:
```
#!/usr/bin/bash

file=$1
grep -o -E '[a-zA-Z\_]+' < "$file" | sort --unique | xargs
```

тестовый файл test.txt:
```
#include <stdio.h>

int main(void) {
    printf("Hello, World!\n");
    return 0;
}

World
int_count
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/test$ ./idens test.txt
h Hello include int int_count main n printf return stdio void World
```

## Задача 5
код bash:
```
#!/usr/bin/bash

chmod +x "$1" && sudo cp "$1" /usr/local/bin/"$1"
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/test$ ./reg idens
cloverix@cloverix-MDG-XX:~/test$ ls /usr/local/bin
idens
```

## Задача 6
код bash:
```
#!/usr/bin/bash

c_js_files=()
py_files=()
while IFS= read -r file; do
        read -r line < "$file"

        if [[ "$file" == *".c" || "$file" == *".js" ]]; then

                if [[ $line == "//"* || $line == "/*"* ]]; then
                        c_js_files+=("$file")
                fi

        elif [[ "$file" == *".py" ]]; then

                if [[ $line == "#"* || $line == "\"\"\""* || $line == "'''"* ]]; then
                        py_files+=("$file")
                fi

        fi
done < <(find "$1" -type f)

echo "Файлы c и js с комментариями:"
echo "${c_js_files[*]}"

echo "Файлы py с комментариями:"
echo "${py_files[*]}"
```

тестовые файлы:
```
cloverix@cloverix-MDG-XX:~/test/testdir$ ls
f.c  f.js  f.py  f2.js  f2.py
cloverix@cloverix-MDG-XX:~/test/testdir$ ls | xargs cat
//Это комментарий
Это не комментарий
"""Комм"""
/*Это опять комментарий*/
\# И это комментарий
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/test$ ./sfc testdir
Файлы c и js с комментариями:
testdir/f.c testdir/f2.js
Файлы py с комментариями:
testdir/f.py testdir/f2.py
```

## Задача 8
код bash:
```
#!/usr/bin/bash

dir=""

# Если нет переданной директории - выходим с ошибкой
if [ -d "$( realpath "$1" )" ]; then
        dir="$( realpath "$1" )"
else
        echo "Directory '$1' not found" >&2
        exit 1
fi

ext=""

# Если расширение неправильное - выходим с ошибкой
if [[ "$2" == .* && "$2" != *[[:space:]]* ]]; then
         ext="$2"
else
         echo "Invalid extension" >&2
         exit 1
fi

files_to_tar=()

# Находим все файлы с нужным расширением, выводим их пути относительно переданной директории и заполняем ими массив
while read -r file; do
        files_to_tar+=( "$file" )
done < <( find "$dir" -type f -name "*$ext" -printf "%P\n" )

# Переходим в переданную директорию и пакуем файлы
tar -C "$dir" -f "$dir".tar -c "${files_to_tar[@]}"
```

тестовая директория:
```
cloverix@cloverix-MDG-XX:~/xxx$ ls dir
'file 3.tr'  'file 4.tr'   file1.tr   file2.tr
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/xxx$ ./tarext dir .tr
cloverix@cloverix-MDG-XX:~/xxx$ tar -xvf dir.tar
file2.tr
file 4.tr
file1.tr
file 3.tr
```

## Задача 10
код bash:
```
#!/usr/bin/bash

dir="$1"
find "$dir" -maxdepth 1 -type f -size 0 -printf "%P\n"
```

тестовая директория:
```
cloverix@cloverix-MDG-XX:~/xxx$ ls -la files
total 16
drwxrwxr-x 2 cloverix cloverix 4096 Sep 19 23:45 .
drwxrwxr-x 3 cloverix cloverix 4096 Sep 19 23:49 ..
-rw-rw-r-- 1 cloverix cloverix    0 Sep 19 23:45 file1
-rw-rw-r-- 1 cloverix cloverix    0 Sep 19 23:45 file2
-rw-rw-r-- 1 cloverix cloverix    7 Sep 19 23:46 file3
-rw-rw-r-- 1 cloverix cloverix    0 Sep 19 23:45 file4
-rw-rw-r-- 1 cloverix cloverix   14 Sep 19 23:46 file5
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/xxx$ ./sempty files
file1
file2
file4
```

#!/usr/bin/env bash

if [ "$1" == "1" ]; then
    echo "Запуск ПР №1 (Эмулятор терминала)..."
    python3 src/prac-1/window.py
elif [ "$1" == "2" ]; then
    echo "Запуск ПР №2 (Граф зависимостей)..."
    python3 src/prac-2/apk_deps.py
else
    echo "Использование: ./run.sh [номер_работы]"
    echo "Пример: ./run.sh 1  (для ПР1)"
    echo "Пример: ./run.sh 2  (для ПР2)"
fi
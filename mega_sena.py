#fazer um jogo igual a megasena
import os 
import random
import time
import tkinter as tk

numeros_jogados =[]
numeros_sorteados =[]





for i in range(6):
    r = int(input("Quais os números da vez? "))
    numeros_jogados.append(r)
for j in range(6):
    numero = random.randint(1,60)
    numeros_sorteados.append(numero)
if numeros_jogados == numeros_sorteados:
    print("\nNúmeros jogados: ", numeros_jogados)
    time.sleep(20)
    print("...")
    time.sleep(20)
    print("\nNúmeros Sorteados: ", numeros_sorteados)
    time.sleep(10)
    print("Parabéns! Você foi sorteado\n")
else:
    print("\nNúmeros jogados: ", numeros_jogados)
    time.sleep(20)
    print("...")
    time.sleep(20)
    print("Os números sorteados foram: \n", numeros_sorteados)
    time.sleep(10)

    print("Não foi dessa vez! \n")

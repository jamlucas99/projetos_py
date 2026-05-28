# deve calcular comissão
# comissão é definida com base no valor das vendas
# formula: vendas + %das vendas + 200
valores = []


def def_Func():

    nome = input("Qual o nome do funcionário? ")
    vendas = float(input("Quantos ele vendeu? "))

    comissao = vendas * 0.09
    salario_final = vendas + comissao + 200

    return f'''
Funcionário: {nome}
Vendas: R$ {vendas:.2f}
Comissão: R$ {comissao:.2f}
Salário Final: R$ {salario_final:.2f}
'''


def saida():

    for i in range(3): 

        f = def_Func()
        valores.append(f)

    print("\nRESULTADO:\n")

    for item in valores:
        print(item)


if __name__ == '__main__':

    saida()

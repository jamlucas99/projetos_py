contas = []

while True:
    nome = input("Descreva o gasto: ")
    valor = float(input("R$: "))
    data = input("Data em dd/mm/aa: ")

    contas.append({
        "nome": nome,
        "valor": valor,
        "data": data
    })

    q = input("Você tem dívidas para adicionar? (S/N): ").strip().lower()

    if q not in ("s", "n"):
        print("Opção inválida, apenas preencha com s ou n")
    elif q == "s":
        continue
    else:
        break

print("\nContas cadastradas:")
for conta in contas:
    print(conta)
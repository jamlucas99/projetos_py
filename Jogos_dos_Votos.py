

qnt_VotosWS = 1
qnt_VotosUNIX = 1
qnt_VotosLinux = 1


                
while True:


    
    total = qnt_VotosWS + qnt_VotosUNIX + qnt_VotosLinux
    pct_WS = (qnt_VotosWS / total) * 100
    pct_Unix = (qnt_VotosUNIX / total) * 100
    pct_linux = (qnt_VotosLinux / total) * 100


    so = input('''Em qual sistema operacional você irá votar? 
                  1. Windows Server
                  2. Unix
                  3. Linux''')
    if so in  "Windows Server" or so == "1":
        qnt_VotosWS += 1
    elif so in "Unix" or so == "2":
        qnt_VotosUNIX += 1
    elif so in "Linux" or so == "3":
        qnt_VotosLinux += 1
    else:
        print("Opção errada!")

    
    resultado = f'''
                                        |Sistema Operacional        |Votos                          % 
                                        |-------------------        |-----                         ---
                                        |Windows Server             |{qnt_VotosWS}                      |{pct_WS}%
                                        |Unix                       |{qnt_VotosUNIX}                    |{pct_Unix}%
                                        |Linux                      |{qnt_VotosLinux}                   |{pct_linux}%
                                        |-------------------        |-----         
                                        |Total                      |({total})         
'''


    print(resultado)

    
                


import math
import csv
import os.path

##Implementacao do modelo energetico do Raspberry Pi 2 Model B
# (com excecao do gasto de energia da placa de rede Ethernet cabeada)
#Fonte:
#PowerPi: Measuring and Modeling the Power Consumption of the Raspberry Pi
#Conference Paper · September 2014
#DOI: 10.1109/LCN.2014.6925777
#Conference: IEEE Conference on Local Computer Network


class PowerPi():
    def __init__(self):
        #
        ##componentes da formula (12) Ppi = Pidle + Pcpu + Pwifidle + Pwifiup + Pwifidn
        #constantes da formula (12)
        self.Pidle = 1.5778 #(Table 1)
        self.Pwifidle = 0.942 #(Table 1)

        #variaveis da formula (12)
        self.Ppi=0 #energia consumida (W) durante o tempo de execucao da aplicacao no raspi
        self.Pcpu=0 #energia consumida pelo sistema
        self.Pwifiup=0 #energia consumida pelo envio de mensagens
        self.Pwifidn = 0 #energia consumida pelo recebimento de mensagens

        #
        ##componentes da formula (9) u= (Cbusy[t]-Cbusy[t-1])/(Ctotal[t]-Ctotal[t-1])
        self.u=0

        #Cbusy=Cuser+Cnice+Csystem
        self.Cbusyt=0
        self.Cbusyt_1=0

        #Ctotal=Cbusy+Cidle
        self.Ctotalt=0
        self.Ctotalt_1=0

        self.Cuser=0#Time spent in user mode
        self.Cnice=0#Time spent in user mode with low priority
        self.Csystem=0#Time spent in system mode

        #idle = Time spent in the idle task.
        #This value should be USER_HZ times the second entry in the /proc/uptime pseudo-file
        self.Cidle=0

        ##componentes da formula (10) r[t]=B[t]-B[t-1]/deltaT
        self.deltaT = 0 #tempo em segundos da medicao
        self.t = 0
        self.t_1 = 0

        #taxa de transmissao de envio de dados (Upload)
        self.rWifiUp=0
        self.BtWifiUp=0
        self.Bt_1WifiUp=0
        self.BWifiUp = 0

        #taxa de transmissao de recebimento de dados (Download)
        self.rWifiDn = 0
        self.BtWifiDn=0
        self.Bt_1WifiDn = 0
        self.BWifiDn = 0

        #ampliando a classe para obter mais estatisticas da rede
        #estastisticas de recepcao de dados
        # [1] bytes [2]packets [3]errs [4]drop [5]fifo [6]frame [7]compressed [8]multicast
        #estatisticas de transmissao de dados
        # [9]bytes [10]packets [11]errs [12]drop [13]fifo [14]colls [15]carrier [16]compressed
        self.wifiStatInicial = []
        self.wifiStatFinal = []

    def getCPUCycles(self):
        with open('/proc/stat', 'r') as f:
            data = f.readlines()
            for line in data:
                words = line.split()
                cpu = words[0]
                if cpu == 'cpu':
                    self.Cuser = int(words[1])
                    self.Cnice = int(words[2])
                    self.Csystem = int(words[3])
                    self.Cidle = int(words[4])
                    break

    def getBytes(self):
        netStats=[]
        with open('/proc/net/dev', 'r') as f:
            data = f.readlines()
            for line in data:
                words = line.split()
                wlan0 = words[0]
                if wlan0 == 'wlan0:':
                    netStats = words[:]
                    self.BWifiDn = int(words[1])
                    self.BWifiUp = int(words[9])
                    break

        return netStats


    def getTime(self):
        tempo = 0  # the uptime of the system(seconds)
        with open('/proc/uptime', 'r') as f:
            data = f.readlines()

            for line in data:
                words = line.split()
                tempo = float(words[0])
                break

        return tempo

    #CHAMAR NO INICIO DA EXECUCAO DA APLICACAO: primeiro metodo a ser chamado
    # dentro do construtor da aplicacao que se deseja medir o consumo energetico
    def calcularVart_1(self):
        self.getCPUCycles()
        self.wifiStatInicial=self.getBytes()

        # calcula o tempo em segundos
        self.t_1 = self.getTime()

        # calcula ciclos de CPU
        self.Cbusyt_1 = self.Cuser + self.Cnice + self.Csystem
        self.Ctotalt_1 = self.Cbusyt_1 + self.Cidle

        # calcula Bytes Transmitidos
        self.Bt_1WifiDn = self.BWifiDn
        self.Bt_tWifiUp = self.BWifiUp

    #CHAMAR NO FINAL DA EXECUCAO DA APLICACAO:
    #ultimo metodo a ser chamado na execucao da aplicacao
    def calcularVart(self):
        self.getCPUCycles()
        self.wifiStatFinal=self.getBytes()

        #calcula o tempo final
        self.t = self.getTime()

        #calcula ciclos de CPU do final
        self.Cbusyt= self.Cuser+self.Cnice+self.Csystem
        self.Ctotalt=self.Cbusyt+self.Cidle

        #calcula Bytes Transmitidos do final
        self.BtWifiDn=self.BWifiDn
        self.BtWifiUp=self.BWifiUp

        self.calcularPpi()

    # calcula formula (12): a energia consumida pela aplicacao
    def calcularPpi(self):
        self.calcularPcpu()
        self.calcularPwifi()
        self.Ppi = self.Pidle + self.Pcpu + self.Pwifidle + self.Pwifiup + self.Pwifidn

        print ('Ppi = '+str(self.Ppi))

    def calcularPcpu(self):
        self.u = (self.Cbusyt - self.Cbusyt_1)/(self.Ctotalt - self.Cbusyt_1)
        self.Pcpu = 0.181*self.u

    #calculo da formula (10) para taxa em Mbps
    def calcularPwifi(self):
        #calcula tempo em segundos
        self.deltaT = self.t - self.t_1

        mbit = 8/1000000 #para transformar os bytes em Mbit

        self.rWifiDn = (self.BtWifiDn - self.Bt_1WifiDn) * mbit / self.deltaT
        self.rWifiUp = (self.BtWifiUp - self.Bt_1WifiUp) * mbit / self.deltaT

        self.Pwifidn = 0.064 + 4.813 * math.exp(-3) * self.rWifiDn
        self.Pwifiup = 0.064 + 4.813 * math.exp(-3) * self.rWifiUp

    ##CHAMAR DEPOIS DO METODO calcularVart
    # grava informacoes do modelo energetico e outras estatisticas de rede de dados
    # em um arquivo .csv
    def gravarLog(self, nome, idTeste):
        nomeArquivo = nome + '.csv'
        header = ['idTeste','Ppi','Pcpu','Pwifiup','Pwifidn',
                  'bytesRx','packetsRx','errsRx','dropRx', 'fifoRx','frameRx','compressedRx','multicastRx',
                  'bytesTx','packetsTx','errsTx','dropTx', 'fifoTx','frameTx','compressedTx','multicastTx',]
        stats = [idTeste,self.Ppi, self.Pcpu, self.Pwifiup, self.Pwifidn]

        for i in range(1,len(self.wifiStatInicial)):
            stat = (int(self.wifiStatFinal[i]) - int(self.wifiStatInicial[i]))
            stats.append(stat)

        if os.path.isfile(nomeArquivo):
            with open(nomeArquivo, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=';',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(stats)
        else:
            with open(nomeArquivo, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=';',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(header)
                writer.writerow(stats)

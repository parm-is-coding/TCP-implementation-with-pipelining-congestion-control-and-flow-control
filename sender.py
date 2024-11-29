from socket import socket,AF_INET,SOCK_DGRAM
import time
from threading import Thread
import math
import struct

serverName = "192.168.1.77"
serverPort = 8080
data = "Hello"
listeningPort = 58900
data = "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHOOO" * 100

senderWindowSize = 10
sendbase = 0
nextseqNumber = 0
timeout = 1
packetsize = 1024

#send Limiters
senderWindowSize = 10
receiverBufferSize = 4096

#socket
sendSocket = socket(AF_INET,SOCK_DGRAM)
recieveSocket = socket(AF_INET,SOCK_DGRAM)
recieveSocket.settimeout(2)
recieveSocket.bind(('',listeningPort))
#retransmit
startTime = time.time()
duplicateACK = 0

acked = [False] * math.ceil(len(data)/packetsize)

#connection management
isConnected = False
isFin = False
isFinSent = False

def Retransmit(seqNumber):
    message = ""
    if((seqNumber+packetsize)<len(data)):
        message = data[seqNumber:seqNumber+packetsize]
    else:
        message = data[seqNumber:]
    packet = makeTCP_Header(message.encode(),seqNumber)
    print(packet)
    #sendSocket.sendto(packet.encode,serverName,serverPort)
    

def timeoutHandler():
    global startTime, duplicateACK, sendbase
    test = 0
    while ((not isFin) and (test <10)):
        currentTime = time.time()
        if((currentTime-startTime > timeout) or (duplicateACK >= 3)):
            Retransmit(sendbase)
            duplicateACK = 0
            startTime = currentTime
            test = test + 1
            print("retransmit")

def sendPacket(message):
    global nextseqNumber
    packet = makeTCP_Header(message.encode(),nextseqNumber)
    nextseqNumber = nextseqNumber + len(message)
    sendSocket.sendto(packet,serverName,serverPort)
    print("Sent")
    
    
def receiveACK():
    while(not isFin):
        try:
            message, Address = recieveSocket.recvfrom(2048)
            sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, data = parse_Header(packetMessage)
            markACK(ackNumber)
            
            print("recieved")
        except socket.timeout:
            if(isFin):
                break
          
    
def makeTCP_Header(data,seqNum):
    flags = 0x02
    recieveBuffer = 4096
    checksum = makeChecksum(data,seqNum,listeningPort,serverPort,flags,recieveBuffer)
    header = struct.pack(
        '!HHIIHHHH', 
        listeningPort,
        serverPort,       
        seqNum,            
        0,                  
        (5 << 12) | flags,  
        recieveBuffer,       
        checksum,
        0
    )
    return header + data
    
def parse_Header(packetMessage):
    sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, urgentPointer = struct.unpack(
        '!HHIIHHHH', packetMessage[:16])
    data = packetMessage[16:]
    return sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, data

def makeChecksum(data,seqNum,listeningPort,serverPort,flags,recieveBuffer):
    header = struct.pack(
        '!HHIIHHHH', 
        listeningPort,
        serverPort,       
        seqNum,            
        0,                  
        (5 << 12) | flags,  
        recieveBuffer,       
        0,
        0
    )
    full_packet = header + data
    checksum = 0
    for i in range(0, len(full_packet), 2):
        word = full_packet[i:i+2]
        if len(word) == 2:
            checksum += (word[0] << 8) + word[1]
        else:
            checksum += (word[0] << 8)
    
    checksum = (checksum >> 16) + (checksum & 0xFFFF)
    checksum = ~checksum & 0xFFFF
    return checksum

def markACK(ackNumb):
    acked[ackNumb // packetsize] = True
    if ackNumb == sendbase:
        while acked[sendbase // packetsize]:
            sendbase += packetsize

def sendHandler():
    while(not isFinSent):
        #Pipelining
        if(nextseqNumber < sendbase + senderWindowSize*packetsize):
            #Flow Control
            if(nextseqNumber-sendbase < receiverBufferSize):
                message = ""
                if((nextseqNumber+packetsize)<len(data)):
                    message = data[nextseqNumber:nextseqNumber+packetsize]
                else:
                    message = data[nextseqNumber:]
                sendPacket(message)
    print("sender")

def main():
    clientSocket = socket(AF_INET,SOCK_DGRAM)
    clientSocket.sendto(data.encode,serverName,serverPort)
    

def main():
    timeoutThread = Thread(target=timeoutHandler)
    timeoutThread.start()
    sendThread = Thread(target=sendHandler)
    sendThread.start()
    receiveThread = Thread(target=receiveACK)
    receiveThread.start()

    sendThread.join()
    receiveThread.join()
    timeoutThread.join()

if __name__ == "__main__":
    main()

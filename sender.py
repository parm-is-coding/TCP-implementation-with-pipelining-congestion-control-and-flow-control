from socket import socket, AF_INET, SOCK_DGRAM
import struct
import time
from threading import Thread,Lock
import random 
import math
import sys

sendbase_lock = Lock()
nextseqNumber_lock = Lock()
cwnd_Lock = Lock()

# Server configuration
if len(sys.argv) != 4:
    print("Usage: python script.py <server_ip> <server_port> <listening_port>")
    sys.exit(1)

serverName = sys.argv[1]
serverPort = int(sys.argv[2])
listeningPort = int(sys.argv[3])
#serverName = "192.168.1.77"
#serverPort = 8080
#listeningPort = 58900
data = "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHOOO" * 100
print(len(data))
# Global variables
sendbase = 0
nextseqNumber = 0
timeout = 1
packetsize = 32
senderWindowSize = 100
receiverBufferSize = 4096
isConnected = False
isFinished = False
isFinSent = False
duplicateACK = 0
startTime = time.time()
endtimer = 0
cruptProbablity = 0.01
lossProbablity = 0.01

congestionWidow = 1
firstLoss = False

# Sockets
sendSocket = socket(AF_INET, SOCK_DGRAM)
recieveSocket = socket(AF_INET, SOCK_DGRAM)
recieveSocket.settimeout(5)
recieveSocket.bind(('', listeningPort))

# Acknowledgment tracking
acked = [False] *((len(data) // packetsize)+1)


def Retransmit(seqNumber):
    """Handles retransmission of packets."""
    global sendSocket, serverName, serverPort, data, packetsize,isFinSent,firstLoss,congestionWidow

    if seqNumber + packetsize < len(data):
        message = data[seqNumber - 1:seqNumber - 1 + packetsize]
    else:
        message = data[seqNumber - 1:]

    if seqNumber + len(message) >= len(data):
        packet = makeTCP_Header(message.encode(), seqNumber, FIN=True)
        isFinSent = True
    else:
        packet = makeTCP_Header(message.encode(), seqNumber)
    if(not firstLoss):
        firstLoss = True
    with cwnd_Lock:
        congestionWidow = math.ceil(congestionWidow / 2)
        print(f"C Window {congestionWidow}")
    packet = cruptMessage(packet)
    if(not isPacketLost()):
        sendSocket.sendto(packet, (serverName, serverPort))


def timeoutHandler():
    """Handles timeout-based retransmission."""
    global startTime, duplicateACK, sendbase, timeout, isFinished,endtimer

    while not isFinished or  time.time() - endtimer < 5:
        currentTime = time.time()
        if (currentTime - startTime > timeout):
            print("timeout retransmit")
            with sendbase_lock:
                Retransmit(sendbase + 1)
            duplicateACK = 0
            startTime = currentTime
        elif((duplicateACK >= 3)):
            print("DuplicateACK retransmit")
            with sendbase_lock:
                Retransmit(sendbase + 1)
            duplicateACK = 0
            startTime = currentTime


def sendPacket(message):
    """Sends a packet."""
    global nextseqNumber, sendSocket, serverName, serverPort, isFinSent, data
    if nextseqNumber == 0:
        packet = makeTCP_Header(message.encode(), nextseqNumber, SYN=True)  # No .encode()
    elif nextseqNumber + len(message) >= len(data):
        packet = makeTCP_Header(message.encode(), nextseqNumber, FIN=True)  # No .encode()
        isFinSent = True
    else:
        packet = makeTCP_Header(message.encode(), nextseqNumber)  # No .encode()
        nextseqNumber += len(message)
    packet = cruptMessage(packet)
    if(not isPacketLost()):
        sendSocket.sendto(packet, (serverName, serverPort))


def receiveACK():
    """Receives and processes acknowledgments."""
    global isFinished, acked, duplicateACK, startTime,data,receiverBufferSize

    while not isFinished or  time.time() - endtimer < 5:
        try:
            message, address = recieveSocket.recvfrom(2048)
            sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, messagedata, isSYN, isACK, isFIN = parse_Header(
                message)
            isCrupt = checkCrupt(sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, messagedata)
            if isCrupt:
                receiverBufferSize = recBuf
                if isFIN:
                    isFinished = True
                    endtimer = time.time()
                if isACK:
                    if ackNumber - 1 <= len(data):
                        if acked[((ackNumber - 1) // packetsize)-1]:
                            duplicateACK += 1
                        else:
                            duplicateACK = 0  # Reset on valid new ACK
                            markACK(ackNumber - 1)
                            startTime = time.time()  # Reset timeout
        except TimeoutError:
            continue

def markACK(ackNumb):
    """Marks an acknowledgment and updates the sendbase."""
    global sendbase, packetsize, acked, data, congestionWidow, firstLoss

    segment_idx = (ackNumb // packetsize)
    with sendbase_lock:
        for i in range((sendbase // packetsize), segment_idx):
            acked[i] = True
            with cwnd_Lock:
                if firstLoss:
                    congestionWidow = congestionWidow + 1
                else:
                    congestionWidow = congestionWidow * 2
                print(f"C Window {congestionWidow}")
        while sendbase < len(data) and acked[sendbase // packetsize]:
            sendbase += packetsize


def makeTCP_Header(data, seqNum, SYN=False, ACK=False, FIN=False):
    """Creates a TCP-like header."""
    recieveBuffer = 4096
    flags = set_flags(SYN, ACK, FIN)
    checksum = makeChecksum(data, seqNum, listeningPort, serverPort, flags, recieveBuffer)
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
    """Parses a received packet header."""
    sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, urgentPointer = struct.unpack(
        '!HHIIHHHH', packetMessage[:20])
    data = packetMessage[20:]
    is_SYN = flags & 0x02 != 0
    is_ACK = flags & 0x10 != 0
    is_FIN = flags & 0x01 != 0
    return sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, data, is_SYN, is_ACK, is_FIN


def makeChecksum(data, seqNum, listeningPort, serverPort, flags, recieveBuffer):
    """Calculates checksum for error detection."""
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
        word = full_packet[i:i + 2]
        if len(word) == 2:
            checksum += (word[0] << 8) + word[1]
        else:
            checksum += (word[0] << 8)

    checksum = (checksum >> 16) + (checksum & 0xFFFF)
    checksum = ~checksum & 0xFFFF
    return checksum

def checkCrupt(sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum_answer, data):
    header = struct.pack(
        '!HHIIHHHH', 
        sPort,          # Source Port
        dPort,       # Destination Port
        seqNumber,              # Sequence Number
        ackNumber,                   # Acknowledgment Number
        (5 << 12) | flags,   # Header length and flags
        recBuf,       # Receive Window Size
        0,                   # Checksum
        0                    # Urgent Pointer
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
    if(checksum == checksum_answer):
        return True
    else:
        return False



def sendHandler():
    """Manages packet sending in the pipeline."""
    global isFinSent,nextseqNumber,sendbase,senderWindowSize,packetsize,receiverBufferSize,congestionWidow

    while not isFinSent:
        with sendbase_lock:
            with nextseqNumber_lock:
                if nextseqNumber - 1 < sendbase + senderWindowSize * packetsize:
                    if (nextseqNumber - 1 - sendbase < receiverBufferSize) and ((nextseqNumber - 1 - sendbase)//packetsize) <= congestionWidow:
                        message = data[nextseqNumber - 1: nextseqNumber - 1 + packetsize]
                        sendPacket(message)
                    


def set_flags(syn=False, ack=False, fin=False):
    """Sets TCP flags."""
    flags = 0
    if syn:
        flags |= 0x02
    if ack:
        flags |= 0x10
    if fin:
        flags |= 0x01
    return flags


def connect():
    """Handles the connection handshake."""
    global receiverBufferSize, serverName, serverPort, nextseqNumber, isConnected

    while not isConnected:
        packet = makeTCP_Header("".encode(), 0, SYN=True)
        sendSocket.sendto(packet, (serverName, serverPort))
        try:
            rec_message, address = recieveSocket.recvfrom(2048)
            _, _, _, ackNumber, _, recBuf, _, _, isSYN, isACK, _ = parse_Header(rec_message)
            if isSYN and isACK and ackNumber == 1:
                receiverBufferSize = recBuf
                with nextseqNumber_lock:
                    nextseqNumber = 1
                isConnected = True
        except TimeoutError:
            print("Retrying connection...")

def cruptMessage(packet):
    global cruptProbablity
    temp = random.random()
    if temp <= cruptProbablity:
        byte_array = bytearray(packet)
        if len(byte_array) > 0:
            index = random.randint(0, len(byte_array) - 1)
            bit = 1 << random.randint(0, 7)
            byte_array[index] ^= bit
        return bytes(byte_array)
    else:
        return packet

def isPacketLost():
    global lossProbablity
    temp = random.random()
    if temp <= lossProbablity:
        return True
    else:
        return False

def main():
    global startTime
    connect()
    startTime = time.time()
    timeoutThread = Thread(target=timeoutHandler)
    sendThread = Thread(target=sendHandler)
    receiveThread = Thread(target=receiveACK)

    timeoutThread.start()
    receiveThread.start()
    sendThread.start()

    sendThread.join()
    receiveThread.join()
    timeoutThread.join()


if __name__ == "__main__":
    main()

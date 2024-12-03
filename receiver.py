from socket import socket, AF_INET, SOCK_DGRAM
import struct
import time
import random

# Receiver configuration
serverPort = 8080
packetsize = 32
receiverWindowSize = 100
availableBuffer = 4096
receiverBuffer = {}
receivedData = bytearray()
expectedSeqNumber = 1
isConnected = False
isFinReceived = False
isFinished = False
lastSeq = -1
cruptProbablity = 0.01
lossProbablity = 0.01
endtimer = 0
 

# Create sockets
receiverSocket = socket(AF_INET, SOCK_DGRAM)
receiverSocket.bind(('', serverPort))
receiverSocket.settimeout(5)  # Timeout for the receiver

def makeTCP_Header(data, seqNum, ackNum,destPort, SYN=False, ACK=False, FIN=False):
    global serverPort,availableBuffer
    flags = set_flags(SYN, ACK, FIN)
    checksum = makeChecksum(data, seqNum, destPort, serverPort, flags, availableBuffer,ackNum)
    header = struct.pack(
        '!HHIIHHHH', 
        serverPort,          # Source Port
        destPort,       # Destination Port
        seqNum,              # Sequence Number
        ackNum,              # Acknowledgment Number
        (5 << 12) | flags,   # Header length and flags
        availableBuffer,  # Receiver Window Size
        checksum,            # Checksum
        0                    # Urgent Pointer
    )
    return header + data

def parse_Header(packetMessage):
    sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, urgentPointer = struct.unpack(
        '!HHIIHHHH', packetMessage[:20])
    data = packetMessage[20:]
    is_SYN = flags & 0x02 != 0  # Check if SYN is set
    is_ACK = flags & 0x10 != 0  # Check if ACK is set
    is_FIN = flags & 0x01 != 0  # Check if FIN is set
    return sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, data, is_SYN, is_ACK, is_FIN

def makeChecksum(data, seqNum, listeningPort, serverPort, flags, receiveBuffer,ackNumber):
    header = struct.pack(
        '!HHIIHHHH', 
        serverPort,          # Source Port
        listeningPort,       # Destination Port
        seqNum,              # Sequence Number
        ackNumber,                   # Acknowledgment Number
        (5 << 12) | flags,   # Header length and flags
        receiveBuffer,       # Receive Window Size
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
    return checksum

def set_flags(syn=False, ack=False, fin=False):
    flags = 0
    if syn:
        flags |= 0x02  # Set SYN bit
    if ack:
        flags |= 0x10  # Set ACK bit
    if fin:
        flags |= 0x01  # Set FIN bit
    return flags

def sendACK(seqNumber, ackNumber, ip,dPort,SYN=False, FIN=False):
    global lastSeq,isFinished,isFinReceived, endtimer
    if((ackNumber == lastSeq) and isFinReceived ):
        ackPacket = makeTCP_Header(b"", seqNumber, ackNumber,dPort, SYN=SYN, ACK=True, FIN=True)
        isFinished = True
        endtimer = time.time()
    else:
        ackPacket = makeTCP_Header(b"", seqNumber, ackNumber, dPort,SYN=SYN, ACK=True, FIN=FIN)
    ackPacket = cruptMessage(ackPacket)
    if (not isPacketLost()):
        receiverSocket.sendto(ackPacket, (ip,dPort))

def handleConnection():
    global isConnected, endtimer, isFinReceived, expectedSeqNumber, receiverBuffer, receivedData, availableBuffer,isFinished,lastSeq
    while not isFinished or  time.time() - endtimer < 5:
        try:
            packet, address = receiverSocket.recvfrom(2048)
            sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, data, is_SYN, is_ACK, is_FIN = parse_Header(packet)
            isNotCrupt = checkCrupt(sPort, dPort, seqNumber, ackNumber, flags, recBuf, checksum, data)
            if isNotCrupt:
                ip = address[0]
                if is_FIN:
                    isFinReceived = True
                    lastSeq = seqNumber + len(data)
                if is_SYN:  # Handle connection setup
                    sendACK(0, 1,ip,sPort, SYN=True)
                elif seqNumber == expectedSeqNumber:  # Handle in-order data
                    receivedData.extend(data)
                    expectedSeqNumber += len(data)
                    # Check for buffered out-of-order packets
                    while expectedSeqNumber in receiverBuffer:
                        tempdata = receiverBuffer.pop(expectedSeqNumber)
                        receivedData.extend(tempdata)
                        expectedSeqNumber += len(tempdata)
                        availableBuffer = availableBuffer + len(tempdata)
                    sendACK(seqNumber, expectedSeqNumber,ip,sPort)
                elif seqNumber > expectedSeqNumber:  # Out-of-order packet
                    if seqNumber not in receiverBuffer:
                        receiverBuffer[seqNumber] = data
                        availableBuffer = availableBuffer - len(data)
                    sendACK(seqNumber, expectedSeqNumber,ip,sPort)
                elif seqNumber < expectedSeqNumber:
                    sendACK(seqNumber, expectedSeqNumber,ip,sPort)

        except TimeoutError:
            if isFinReceived and time.time() - endtimer > 5:
                break
            print("Timeout while waiting for packets.")


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
    print("Receiver is running...")
    handleConnection()
    print("Connection closed. Received data:")
    print(receivedData.decode(errors="ignore"))

if __name__ == "__main__":
    main()
    
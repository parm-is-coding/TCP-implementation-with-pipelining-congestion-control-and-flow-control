from socket import socket,AF_INET,SOCK_DGRAM
import time
import threading
import math

serverName = "192.168.1.77"
serverPort = "8080"
data = "Hello"

senderWindowSize = 10
sendbase = 0
nextseqNumber = 0
timeout = 5
packetsize = 1024
duplicateACK = 0

acked = [False] * math.ceil(len(data)/packetsize)

isConnected = False

def Retransmit(seqNumber):
    #TODO retransmit packet with sequence number
    timer
    
def sendPacket(message):
    packet = makeTCP_Header(message)
    nextseqNumber = nextseqNumber + len(message)
    
    #Send
    
    
    
def receiveACK():
    #recieve
    parse_Header(packetMessage)
    
    
def makeTCP_Header(data):
    
    
def parse_Header(packetMessage):
    
    
    

def main():
    clientSocket = socket(AF_INET,SOCK_DGRAM)
    clientSocket.sendto(data.encode,serverName,serverPort)
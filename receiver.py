from socket import *
import time
import threading

serverPort = 8080

receiverWindowSize = 10
receiverbase = 0
nextseqNumber = 0

isConnected = False




def main():
    serverSocket = socket(AF_INET,SOCK_DGRAM)
    serverSocket.bind(('',serverPort))
    
import socket

IP = "0.0.0.0" #Listen on all interfaces
PORT = 5005 #match the port used by PI sender

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((IP, PORT))
print("Listening UDP on %s:%d ... "% (IP, PORT))
while True:
  data,addr = s.recvfrom(65535)
  host, _ = addrhost, _ = addr
  print(addr, data)

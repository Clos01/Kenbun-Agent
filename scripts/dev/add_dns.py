import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect("192.168.1.183", username="carlos", password="jyZbJ%ljOC&N%kD5", timeout=5)
    stdin, stdout, stderr = ssh.exec_command("sudo -S pihole -a hostrecord vision.lan 100.104.211.61")
    stdin.write("jyZbJ%ljOC&N%kD5\n")
    stdin.flush()
    print(stdout.read().decode())
    print(stderr.read().decode())
except Exception as e:
    print(f"Error: {e}")

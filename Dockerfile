# Base image: Ubuntu 22.04
FROM ubuntu:22.04

# Preseed debconf to auto-approve the tshark install question
RUN echo "wireshark-common wireshark-common/install-setuid boolean true" | debconf-set-selections

# Install core tooling and the SSH service
RUN apt-get update && \
    apt-get install -y \
        openssh-server \
        openssl \
        python3 \
        python3-pip \
        curl \
        wget \
        nmap \
        hashcat \
        tshark \
        john \
        sqlmap\
        sudo && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install sqlmap and the Python requests package
RUN pip3 install sqlmap requests pycryptodome

# Configure the SSH daemon
RUN mkdir /var/run/sshd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 22/' /etc/ssh/sshd_config

# Set the root password to "ctfagent" (customise as needed)
RUN echo 'root:ctfagent' | chpasswd

# Start the SSH service
CMD ["/usr/sbin/sshd", "-D"]

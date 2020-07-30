FROM phusion/baseimage:0.9.16

# set version label
ARG BUILD_DATE
ARG VERSION
LABEL build_version="taius.io version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="ronnieblaze"

# Set correct environment variables
ENV HOME /root
ENV DEBIAN_FRONTEND noninteractive

# Set the locale, to support files that have non-ASCII characters
RUN locale-gen en_US.UTF-8
ENV LC_ALL C.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

# Use baseimage-docker's init system
CMD ["/sbin/my_init"]
RUN mkdir -p /etc/my_init.d

# Disable SSH
RUN rm -rf /etc/service/sshd /etc/my_init.d/00_regen_ssh_host_keys.sh

# Speed up APT
RUN \
echo "force-unsafe-io" > /etc/dpkg/dpkg.cfg.d/02apt-speedup && \
echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache

# Update and Install Packages
RUN \
  add-apt-repository "deb http://us.archive.ubuntu.com/ubuntu/ trusty universe multiverse" && \
  add-apt-repository "deb http://us.archive.ubuntu.com/ubuntu/ trusty-updates universe multiverse" && \
  apt-get update -q && apt-get install -qy \
    python \
    unrar \
    unzip \
    wget \
  && rm -rf /var/lib/apt/lists/*

# Install Maraschino for Plex and clean up
RUN \
  mkdir /opt/maraschino && \
  wget -P /tmp/ https://github.com/ebright/maraschino/archive/master.zip && \
  unzip /tmp/master.zip -d /opt/maraschino && \
  mv /opt/maraschino/maraschino-master/* /opt/maraschino && \
  rm -rf /opt/maraschino/maraschino-master && \
  rm /tmp/master.zip

#set config directory
VOLUME /config /data

#expose ports
EXPOSE 7000

# Add maraschino to runit
RUN mkdir /etc/service/maraschino
COPY maraschino.sh /etc/service/maraschino/run
RUN chmod +x /etc/service/maraschino/run

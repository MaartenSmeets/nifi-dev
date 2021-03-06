#Desktop
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
apt-cache policy docker-ce
add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/ubuntu jammy stable"
apt-get install --no-install-recommends ubuntu-desktop
apt-get -y install aptitude
aptitude -y install --without-recommends ubuntu-desktop 
apt-get -y install gnome-session gnome-terminal tasksel terminator firefox jq apt-transport-https ca-certificates gnupg2 curl software-properties-common docker-ce docker-compose libxss1 libgconf-2-4 evince socat maven openjdk-11-jdk xfonts-terminus fonts-terminus console-terminus mlocate
apt-get -y install --reinstall debconf
tasksel install ubuntu-desktop-minimal
fc-cache -f -v
#Fix root not allowed to start X-window
xhost local:root

#developer user
useradd -d /home/developer -m developer
echo -e "Welcome01\nWelcome01" | passwd developer
usermod -a -G vboxsf developer
usermod -a -G docker developer
usermod -a -G sudo developer
usermod --shell /bin/bash developer

#Hide vagrant
echo '[User]' > /var/lib/AccountsService/users/vagrant
echo 'SystemAccount=true' >> /var/lib/AccountsService/users/vagrant

cp /etc/sudoers.d/vagrant /etc/sudoers.d/developer
sed -i 's/vagrant/developer/g' /etc/sudoers.d/developer

#Disable Wayland
sed -i 's/\#WaylandEnable\=true/WaylandEnable\=false/g' /etc/gdm3/custom.conf
apt-get autoremove
apt-get clean

mkdir /home/developer/comp
cp /vagrant/docker-compose.yml /home/developer/comp

chown -R developer:developer /home/developer/comp
cd /home/developer/comp
docker-compose pull -q

curl https://www.kafkatool.com/download2/offsetexplorer.sh -o /home/developer/kafkatool.sh
chown developer:developer /home/developer/kafkatool.sh

shutdown now -h
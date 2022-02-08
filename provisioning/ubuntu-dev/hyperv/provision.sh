#Desktop
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
apt-cache policy docker-ce
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu impish stable"
apt-get update
apt-get install --no-install-recommends ubuntu-desktop
apt-get -y install aptitude
aptitude -y install --without-recommends ubuntu-desktop 
apt-get -y install gnome-session gnome-terminal tasksel terminator firefox jq apt-transport-https ca-certificates gnupg2 curl software-properties-common docker-ce docker-compose libxss1 libgconf-2-4 evince socat maven openjdk-11-jdk xfonts-terminus fonts-terminus console-terminus mlocate xrdp
apt-get -y install --reinstall debconf
tasksel install ubuntu-desktop-minimal

#Fix root not allowed to start X-window
xhost local:root

#developer user
useradd -d /home/developer -m developer
echo -e "Welcome01\nWelcome01" | passwd developer
usermod -a -G docker developer
usermod -a -G sudo developer
usermod --shell /bin/bash developer

#Hide vagrant
echo '[User]' > /var/lib/AccountsService/users/vagrant
echo 'SystemAccount=true' >> /var/lib/AccountsService/users/vagrant

cp /etc/sudoers.d/vagrant /etc/sudoers.d/developer
sed -i 's/vagrant/developer/g' /etc/sudoers.d/developer
apt-get autoremove
apt-get clean

mkdir /home/developer/comp
cp /vagrant/docker-compose.yml /home/developer/comp

chown -R developer:developer /home/developer/comp
cd /home/developer/comp
docker-compose pull -q

curl https://www.kafkatool.com/download2/offsetexplorer.sh -o /home/developer/kafkatool.sh
chown developer:developer /home/developer/kafkatool.sh

sudo sed -i 's/"quiet splash"/"quiet splash video=hyperv_fb:1920x1080"/g' /etc/default/grub && sudo update-grub

shutdown now -h
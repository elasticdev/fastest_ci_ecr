#apt-get update
#CODE_NAME=`lsb_release -c|cut -d ":" -f 2`
#apt-get install apt-transport-https gnupg -y
#wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | apt-key add -
#echo deb https://aquasecurity.github.io/trivy-repo/deb $CODE_NAME main | tee -a /etc/apt/sources.list.d/trivy.list
#apt-get update
#apt-get install trivy -y
apt-get update
apt-get install wget apt-transport-https gnupg lsb-release apt-transport-https ca-certificates -y
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | apt-key add -
echo deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main | tee -a /etc/apt/sources.list.d/trivy.list
apt-get update
apt-get install trivy

# install
- Install basic raspbery
- create venv for project
```
sudo apt update
sudo apt install python3-pip python3-venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --break-system-packages google-api-python-client google-auth google-auth-oauthlib flask broadlink
```
- clone repository
- to facilitate login
```
ssh -L 8080:localhost:8080 puk@192.168.88.55
```
- now open http://localhost:8080 and login to your account so calendar and google photos could be used byt this app

: 1769134643:0;podman pull quay.io/minio/aistor/minio:RELEASE.2025-12-20T04-58-37Z\
podman run minio/aistor/minio --version
: 1769134921:0;vim $HOME/minio/minio.license
: 1769135017:0;mkdir -p ~/minio/minio.license
: 1769135019:0;vim $HOME/minio/minio.license
: 1769135048:0;cd $HOME/minio/
: 1769135050:0;l
: 1769135063:0;trash-put minio.license
: 1769135068:0;vim $HOME/minio/minio.license
: 1769135081:0;cd -
: 1769135085:0;l
: 1769135292:0;sudo rsync -avP ~/minio /mnt/data/minio 
: 1769135362:0;trash-put ~/minio
: 1769135402:0;l ~
: 1769135464:0;cd minio
: 1769135483:0;trash-put ~/minio
: 1769135488:0;l ~
: 1769135503:0;cd 
: 1769135508:0;cd minio
: 1769135508:0;l
: 1769135524:0;l /var/lib/docker
: 1769135601:0;ps -h
: 1769135644:0;ddf -h
: 1769135647:0;df -h
: 1769135698:0;trash-put ~/Downloads
: 1769135700:0;cd 
: 1769135701:0;l
: 1769135729:0;mkdir Downloads
: 1769135748:0;sudo rsync -avP /mnt/data/Downloads Downloads
: 1769135753:0;cd Downloads
: 1769135753:0;l
: 1769135760:0;mv Downloads/* ./
: 1769135767:0;trash-put Downloads
: 1769135767:0;l
: 1769135798:0;cd 
: 1769135799:0;l
: 1769135871:0;trash-put Music
: 1769135877:0;trash-put Videos
: 1769135897:0;sudo rsync -avP /mnt/data/Music ./
: 1769135905:0;sudo rsync -avP /mnt/data/Videos ./
: 1769135906:0;l
: 1769135960:0;cd Public
: 1769135961:0;l
: 1769135964:0;cd Public
: 1769135964:0;l
: 1769135967:0;cd ..
: 1769135977:0;trash-put Public
: 1769135978:0;l
: 1769135980:0;cd ..
: 1769135981:0;l
: 1769136003:0;df -h
: 1769136083:0;# Ê∏É•ÁÉ∞É¶aptÁºÉ≥Â≠É∏ÔºÉ®ÂÉØØËÉ£ΩÈÉßÉ™ÊÉ¥æÂÉßÉÄÁÉπæMBÂÉ®∞ÊÉµ∞GBÔºÉ©sudo apt clean\
# Ê∏É•ÁÉ∞É¶ÊÉ∑ßÂÉ¶É•ÊÉÄ∏ÔºÉ®Â¶ÇÊÉæÉºÂ≠É∏ÂÉº®ÔºÉ©sudo apt autoremove --purge\
# Ê∏É•ÁÉ∞É¶/tmpÁÉªÆÂΩÉµÔºÉ®ÂΩÉ≥ÂÉ©É≠ÂÉ≠ÉÄÁÉ¥®341MÔºÉ©sudo find /tmp -type f -atime +7 -delete
: 1769136090:0;# Ê∏É•ÁÉ∞É¶aptÁºÉ≥Â≠É∏ÔºÉ®ÂÉØØËÉ£ΩÈÉßÉ™ÊÉ¥æÂÉßÉÄÁÉπæMBÂÉ®∞ÊÉµ∞GBÔºÉ©\
sudo apt clean\
\
# Ê∏É•ÁÉ∞É¶ÊÉ∑ßÂÉ¶É•ÊÉÄ∏ÔºÉ®Â¶ÇÊÉæÉºÂ≠É∏ÂÉº®ÔºÉ©\
sudo apt autoremove --purge\
\
# Ê∏É•ÁÉ∞É¶/tmpÁÉªÆÂΩÉµÔºÉ®ÂΩÉ≥ÂÉ©É≠ÂÉ≠ÉÄÁÉ¥®341MÔºÉ©\
sudo find /tmp -type f -atime +7 -delete
: 1769136109:0;# ÊÉø•ÁÉºÉ´ÊÉ∑•ÂøÉ∑ÁÉªÆÂΩÉµÂ§ßÂ∞ÉØ\
sudo du -sh /var/log\
\
# Ê∏É•ÁÉ∞É¶ÊÉ∑ßÊÉ∑•ÂøÉ∑ÔºÉ®‰øÉΩÁÉµÉπÊÉºÄËøÉ±4ÂÉ±®ÔºÉ©\
sudo journalctl --vacuum-time=4weeks\
\
# ÊÉ®É∂ËÄÉ•ÊÉ¨É©Â§ßÂ∞ÉØÊ∏É•ÁÉ∞É¶ÔºÉ®‰øÉΩÁÉµÉπ500MBÔºÉ©\
sudo journalctl --vacuum-size=500M\

: 1769136135:0;# ÊÉø•ÊÉ©æÊÉÄπÂÉ®É¶ÂÉ¨∫Â§ß‰∫ÉÆ1GÁÉ∫É§ÊÉ∂Éß‰ª∂\
sudo find / -xdev -type f -size +1G 2>/dev/null\
\
# ÊÉø•ÁÉºÉ´ÂÉ∞É§ÁÉªÆÂΩÉµÂÉ≠ÉÄÁÉ¥®ÊÉ£É•ÂÉ¶µÔºÉ®ÊÉÄπÂÉ®É¶ÂÉ¨∫ÔºÉ©\
sudo du -h --max-depth=1 / 2>/dev/null | sort -hr\

: 1769136312:0;# ÊÉø•ÁÉºÉ´Â∑≤ÂÆÉ©Ë£É•ÁÉ∫É§snapÂÉ¨É•\
snap list --all\
\
# ÂÉ®ÉÄÈÉπ§Â∑≤Á¶ÅÁÉ¥®ÁÉ∫É§ÊÉ∑ßÁÉ©É®ÊÉº¨ÔºÉ®ÂÉ•≥ÈÉ¥ÆÔºÅÔºÉ©\
sudo snap remove --revision <revision_number> <package_name>\
\
# ‰∏ÄÈÉ¥ÆÊ∏É•ÁÉ∞É¶ÊÉ©ÄÊÉºÉ©ÊÉ∑ßÁÉ©É®ÊÉº¨ÔºÉ®ÊÉÆ®ËÉ≠É∞ÔºÉ©\
#!/bin/bash\
for snapname in $(snap list --all | awk '/disabled/{print $1","$3}'); do\
  IFS=',' read name rev <<< "$snapname"\
  sudo snap remove "$name" --revision="$rev"\
done\
\
# Ê∏É•ÁÉ∞É¶snapÁºÉ≥Â≠É∏\
sudo rm -rf /var/lib/snapd/cache/*\

: 1769136343:0;cd tmp
: 1769136344:0;l
: 1769136361:0;vim auto-clean.sh
: 1769136370:0;qwen
: 1769138356:0;l
: 1769138361:0;vim auto-clean.sh
: 1769138481:0;chmod +x auto-clean.sh
: 1769138487:0;sudo ./auto-clean.sh
: 1769138493:0;sudo ./auto-clean.sh -y
: 1769138505:0;sudo ./auto-clean.sh 
: 1769138506:0;l
: 1769138511:0;vim auto-clean.sh
: 1769138535:0;mv auto-clean.sh ./
: 1769138548:0;mv auto-clean.sh ~
: 1769138549:0;cd ..
: 1769138557:0;./auto-clean.sh -y
: 1769138560:0;./auto-clean.sh 
: 1769138568:0;vim auto-clean.sh
: 1769138620:0;curl -L https://github.com/minio/certgen/releases/latest/download/certgen-linux-amd64 -o certgen\
chmod +x certgen\
sudo mv certgen /usr/local/bin/\

: 1769138635:0;mkdir -p $HOME/minio/certs\
cd $HOME/minio/certs\
certgen -host "127.0.0.1,localhost"\

: 1769138672:0;l
: 1769138677:0;cd ..
: 1769138678:0;l
: 1769138707:0;mkdir minio.license
: 1769138756:0;cat minio.license> free_license.txt
: 1769138759:0;cat free_license.txt
: 1769138764:0;rm minio.license
: 1769138766:0;mkdir minio.license
: 1769138771:0;mv free_license.txt minio.license
: 1769138772:0;l
: 1769138800:0;podman run -dt                                             \\
  -p 9000:9000 -p 9001:9001                                \\
  -v $HOME/minio/data:/mnt/data                            \\
  -v $HOME/minio/minio.license:/minio.license              \\
  -v $HOME/minio/certs:/etc/minio/certs                    \\
  --name "aistor-server"                                   \\
  quay.io/minio/aistor/minio:latest minio server /mnt/data \\
  --license /minio.license\
podman logs aistor-server\

: 1769138893:0;podman pull quay.io/minio/aistor/minio:RELEASE.2025-12-20T04-58-37Z\
podman run minio/aistor/minio --version
: 1769138914:0;which podman
: 1769138918:0;l
: 1769138921:0;l 
: 1769138926:0;l ~
: 1769138944:0;l
: 1769138952:0;podman run -dt                                             \\
  -p 9000:9000 -p 9001:9001                                \\
  -v $HOME/minio/data:/mnt/data                            \\
  -v $HOME/minio/minio.license:/minio.license              \\
  -v $HOME/minio/certs:/etc/minio/certs                    \\
  --name "aistor-server"                                   \\
  quay.io/minio/aistor/minio:latest minio server /mnt/data \\
  --license /minio.license\
podman logs aistor-server\

: 1769138967:0;mkdir data
: 1769138969:0;podman run -dt                                             \\
  -p 9000:9000 -p 9001:9001                                \\
  -v $HOME/minio/data:/mnt/data                            \\
  -v $HOME/minio/minio.license:/minio.license              \\
  -v $HOME/minio/certs:/etc/minio/certs                    \\
  --name "aistor-server"                                   \\
  quay.io/minio/aistor/minio:latest minio server /mnt/data \\
  --license /minio.license\
podman logs aistor-server\

: 1769139582:0;l
: 1769139635:0;ls -la minio/certs/\

: 1769139642:0;l certs
: 1769139682:0;podman ps -a | grep aistor-server
: 1769139700:0;podman logs aistor-server
: 1769139706:0;11;rgb:0b0b/2727/3232;1R
: 1769139708:0;l
: 1769139721:0;mv minio.license minio.license.bk
: 1769139728:0;mv minio.license.bk/free_license.txt ./
: 1769139729:0;l
: 1769139735:0;mv free_license.txt minio.license
: 1769139745:0;trash-put minio.license.bk
: 1769139745:0;l
: 1769139762:0;-
: 1769139774:0;podman restart aistor-server
: 1769139786:0;podman logs aistor-server
: 1769139805:0;podman run -dt                                             \\
  -p 9000:9000 -p 9001:9001                                \\
  -v $HOME/minio/data:/mnt/data                            \\
  -v $HOME/minio/minio.license:/minio.license              \\
  -v $HOME/minio/certs:/etc/minio/certs                    \\
  --name "aistor-server"                                   \\
  quay.io/minio/aistor/minio:latest minio server /mnt/data \\
  --license /minio.license\
podman logs aistor-server\

: 1769139833:0;podman rm aistor-server
: 1769139835:0;podman run -dt                                             \\
  -p 9000:9000 -p 9001:9001                                \\
  -v $HOME/minio/data:/mnt/data                            \\
  -v $HOME/minio/minio.license:/minio.license              \\
  -v $HOME/minio/certs:/etc/minio/certs                    \\
  --name "aistor-server"                                   \\
  quay.io/minio/aistor/minio:latest minio server /mnt/data \\
  --license /minio.license\
podman logs aistor-server\

: 1769139841:0;podman logs aistor-server
: 1769139897:0;podman logs aistor-server -f
: 1769139901:0;podman logs aistor-server 
: 1769140540:0;curl -O https://dl.min.io/client/mc/release/linux-amd64/mcchmod +x mcsudo mv mc /usr/local/bin/
: 1769140550:0;curl -O https://dl.min.io/client/mc/release/linux-amd64/mc\
chmod +x mc\
sudo mv mc /usr/local/bin/
: 1769140564:0;mc --version
: 1769140605:0;.
: 1769140612:0;mc alias set myminio http://127.0.0.1:9000 minioadmin minioadmin\

: 1769140617:0;mc admin info myminio
: 1769140636:0;mc admin user svcacct edit myminio minioadmin
: 1769140688:0;mc admin user change-password myminio minioadmin
: 1769140780:0;mc alias remove myminio\

: 1769140828:0;podman stop aistor-server
: 1769140833:0;podman rm aistor-server\

: 1769140852:0;cd ..
: 1769140852:0;l
: 1769140871:0;vim .minio_env
: 1769140914:0;chmod 600 .minio_env
: 1769140957:0;podman run -dt                                             \\
  -p 9000:9000 -p 9001:9001                                \\
  -v $HOME/minio/data:/mnt/data                            \\
  -v $HOME/minio/minio.license:/minio.license              \\
  -v $HOME/minio/certs:/etc/minio/certs                    \\
  --name "aistor-server"                                   \\
  quay.io/minio/aistor/minio:latest minio server /mnt/data \\
  --license /minio.license\
podman logs aistor-server\

: 1769140991:0;l
: 1769140995:0;pwd
: 1769141022:0;podman stop aistor-server
: 1769141033:0;podman rm aistor-server\

: 1769141060:0;# ‰ΩøÁÉ¥®.envÊÉ∂Éß‰ª∂ÂÉ∞ØÂÉ™®ÂÆπÂÉπ®\
podman run -dt \\
  -p 9000:9000 -p 9001:9001 \\
  --env-file ~/minio/.minio_env \\
  -v $HOME/minio/data:/mnt/data \\
  -v $HOME/minio/minio.license:/minio.license \\
  -v $HOME/minio/certs:/etc/minio/certs \\
  --name "aistor-server" \\
  quay.io/minio/aistor/minio:latest minio server /mnt/data \\
  --license /minio.license\

: 1769141077:0;vim podman_run.txt
: 1769153536:0;cd -
: 1769153542:0;cd ~/Documents/Graduate/02_Research/
: 1769153543:0;l
: 1769157615:0;podman ps
: 1769227281:0;l
: 1769227327:0;cp -r 03_Multi-ACMG-Simple-demo 04_Multi-ACMG-MinerU-demo
: 1769227333:0;l
: 1769227350:0;mv 04_Multi-ACMG-MinerU-demo 05_Multi-ACMG-MinerU-demo
: 1769228072:0;cd 03_Multi-ACMG-Simple-demo
: 1769228074:0;git clone git@github.com:lanshi17/Multilingual-Document-Evidence-Collection-Platform.git\

: 1769228120:0;cd Multilingual-Document-Evidence-Collection-Platform
: 1769228121:0;l
: 1769228159:0;git checkout -b dev-simple-demo
: 1769228401:0;l
: 1769228414:0;rm README.md docker-compose.yml
: 1769228415:0;l
: 1769228426:0;rm .gitignore
: 1769228427:0;l
: 1769228804:0;mv * ../
: 1769228806:0;l
: 1769228820:0;sudo mv .git ../
: 1769228823:0;l
: 1769228826:0;cd ..
: 1769228833:0;rm -r Multilingual-Document-Evidence-Collection-Platform
: 1769228834:0;l
: 1769237821:0;cd ../05_Multi-ACMG-MinerU-demo
: 1769237821:0;l
: 1769237829:0;git clone git@github.com:lanshi17/Multilingual-Document-Evidence-Collection-Platform.git\

: 1769237854:0;sudo mv Multilingual-Document-Evidence-Collection-Platform/.git ./
: 1769237877:0;mv Multilingual-Document-Evidence-Collection-Platform/LICENSE ./
: 1769237878:0;l
: 1769237882:0;l Multilingual-Document-Evidence-Collection-Platform
: 1769237888:0;rm -r Multilingual-Document-Evidence-Collection-Platform
: 1769237917:0;git checkout -b dev-MinerU-demo
: 1769237919:0;l
: 1769248156:0;curl --location --request GET 'https://mineru.net/api/v4/extract-results/batch/6745f16c-ae52-45a1-b7df-5df9cb1569bf' \\
--header 'Authorization: Bearer *****' \\
--header 'Accept: */*'

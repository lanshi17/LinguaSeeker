: 1768490170:0;cd apps/backend
: 1768490171:0;ls
: 1768490208:0;uv run main.py
: 1768995780:0;source /mnt/data/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/.venv/bin/activate
: 1768995780:0;clear
: 1768995786:0;which pthon
: 1768995789:0;which python
: 1768995795:0;cd apps/backend
: 1768995796:0;ls
: 1768995804:0;python
: 1768996134:0;source /mnt/data/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/.venv/bin/activate
: 1768996134:0;clear
: 1768996150:0;cd apps/backend
: 1768996187:0;mv .env.production .env.development
: 1768996205:0;cp .env.example .env.production
: 1768999307:0;ls
: 1768999308:0;l
: 1768999318:0;python
: 1769003175:0;./run_tests.sh pubmed
: 1769047229:0;git rm --cached .env.*
: 1769047267:0;git rm --cached .env.* 2>/dev/null\

: 1769047292:0;git rm --cached apps/backend/.env.development\

: 1769047297:0;git rm --cached apps/backend/.env.*\

: 1769047312:0;git rm --cached apps/backend/.env.production\

: 1769047319:0;git rm --cached apps/backend/.env.test\

: 1769050337:0;chmod +x deploy/check_environment.sh\
./deploy/check_environment.sh\

: 1769050588:0;chmod +x deploy/dev_start.sh\
./deploy/dev_start.sh\

: 1769051526:0;npm install
: 1769051541:0;rm package-lock.json
: 1769051547:0;cd apps/frontend
: 1769051549:0;npm install
: 1769051686:0;pwd
: 1769052380:0;npm install
: 1769052389:0;rm package-lock.json
: 1769052391:0;cd apps/frontend
: 1769052393:0;npm install
: 1769052412:0;npm run 
: 1769052424:0;react-scripts start
: 1769052454:0;npm start
: 1769052503:0;ssh -L 3000:localhost:3000 nps-client\

: 1769052992:0;cd apps/frontend
: 1769052997:0;npm start &
: 1769053038:0;cd apps/backend
: 1769053040:0;l
: 1769053217:0;uv run main.py
: 1769054883:0;codex
: 1769063874:0;cd apps/backend
: 1769063879:0;cd apps/frontend
: 1769063883:0;npm start &
: 1769063892:0;uv run main.py
: 1769063913:0;uv add python-multipart
: 1769063921:0;uv run main.py
: 1769063928:0;codex
: 1769064601:0;uv run main.py
: 1769064749:0;find /proc/*/stat -exec grep -H ' Z ' {} \; | awk '{print $1}' | cut -d'/' -f3 | xargs kill -SIGCHLD\

: 1769064799:0;kill -HUP $(ps aux | awk '{if ($8=="Z") print $2}')\

: 1769064827:0;pkill -s Z\

: 1769064852:0;aux
: 1769064870:0;ps aux
: 1769064916:0;htop
: 1769065109:0;clear
: 1769065121:0;uv run main.py
: 1769065709:0;npm start &
: 1769065731:0;uv run main.py
: 1769066343:0;npm start &
: 1769067165:0;source /mnt/data/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/.venv/bin/activate
: 1769067165:0;clear
: 1769067168:0;npm install -g react-devtools
: 1769067343:0;sudo npm install -g react-devtools
: 1769067650:0;sudo npm install -g npm@11.8.0
: 1769067666:0;uv run main.py
: 1769073233:0;cd apps/frontend
: 1769073238:0;npm start &
: 1769073247:0;cd apps/backend
: 1769073252:0;uv run main.py
: 1769076570:0;cd apps/backend
: 1769076573:0;uv add pdfplumber
: 1769076579:0;uv run main.py
: 1769393310:0;uv run main.py "inputs/åƒ¿ºåƒ»ƒ€æ£€ æµƒ«æƒ·©æƒ¼ƒ¿è¯ƒªæƒ¶­å®¶æƒ·ƒ¯æ€§é«ƒ¸èƒ£ƒ¦åƒ»ºéƒ¦ƒ§èƒ€çƒ·ƒ§ä¸€å®¶ç³»ä¸´åºƒªåƒ¯ƒªéƒ·ä¼ƒ€çƒ©¹ç‚¹åƒ¨ƒ¦æƒ¾ƒ°_å¾ƒ°å³°.pdf" --out-dir outputs/zh
: 1769401625:0;cd apps/backend
: 1769401626:0;l
: 1769401629:0;tree
: 1769401649:0;cd src
: 1769401651:0;tree
: 1769401991:0;cp -r ../03_Multi-ACMG-Simple-demo/src/infrastructure/utils  utils
: 1769402006:0;cp -r ../../../03_Multi-ACMG-Simple-demo/src/infrastructure/utils  utils
: 1769402020:0;cp -r ../../../../03_Multi-ACMG-Simple-demo/src/infrastructure/utils  utils

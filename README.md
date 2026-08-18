Phantom Selfbot
Discord selfbot cu voice looper, spam commands și fun commands.
Features
Voice: intră în voice channels, DM calls, group calls și cântă audio pe loop la volum maxim
Spam: single-line, multi-line, repeated, spiced, global
Fun: ship, gay, pula, call, avatar, userbanner, afkcheck
Owner-only: rename, move, add/remove tokens
Stack
Python 3.11+
discord.py-self (fork cu suport selfbot)
FFmpeg (pentru procesare audio)
PyNaCl (pentru voce opus)
Comenzi Voice (prefix ,)
Comandă
Descriere
,jvc <canal_id> [nr]
Intră în voice channel și cântă
,dmjvc <user_id> [nr]
Voice call DM 1-la-1
,groupjvc <grup_id> [nr]
Voice call grup DM
,stop
Oprește și iese
,stopall
Oprește din tot
,swap <nr/name>
Schimbă melodia
,lista
Lista melodii
,addaudio <url/attach>
Adaugă audio (YouTube sau fișier)
,processall
Reprocesează toate melodiile loud
,rename <nr> <nume>
Redenumește melodie (owner only)
,move <nr> <nr_nou>
Mută melodia pe alt slot (owner only)
,addtoken <tok>
Adaugă token (owner only)
,removetoken <n>
Șterge token (owner only)
,help
Meniu comenzi
Structură fișiere
selfbot/
  bot.py              # cod principal (~1900 linii)
  tokens.txt          # tokenuri Discord (unul per linie)
  requirements.txt    # dependințe Python
  config.json         # config prefix spam
  01.mp3, 02.mp3...   # fișiere audio
  __loud_*.wav        # cache audio procesat (auto-generat)
Instalare locală
pip install -r requirements.txt
# asigură-te că ffmpeg e instalat:
# apt-get install ffmpeg  (Linux)
# brew install ffmpeg    (Mac)
python bot.py
Deploy Render.com
Vezi RENDER_DEPLOY.md pentru instrucțiuni complete.
Licență
Strict pentru uz personal. Selfbot-urile încalcă TOS Discord — folosește pe propriul risc.

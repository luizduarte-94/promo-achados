// Bot Espelho — lê mensagens dos grupos de promoções monitorados e:
//   (1) grava cada uma em ../data/espelho_inbox.jsonl  (sinal de tendência p/ o backend)
//   (2) opcional: reencaminha o texto (sem links) p/ um WhatsApp de destino (modelo antigo)
//
// O backend Python (backend/espelho.py) lê o inbox, extrai o NOME do produto e
// busca nas APIs/scrapers, gerando oferta com LINK e COPY próprios.
// NUNCA copiamos o texto dos outros grupos — só usamos qual produto bomba.
//
// AVISO: whatsapp-web.js é cliente NÃO-OFICIAL do WhatsApp. Viola os Termos de
// Uso e pode BANIR o número. Use SEMPRE um número DEDICADO, nunca o principal.

const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const fs = require('fs');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

// ============== CONFIGURAÇÕES (via .env da raiz do projeto) ==============

// Grupos a espelhar: nomes EXATOS separados por vírgula. Vazio = TODOS os grupos.
const GRUPOS_PERMITIDOS = (process.env.ESPELHO_GRUPOS || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

// Reencaminhar a mensagem (sem links) p/ outro WhatsApp? Default OFF (o fluxo
// novo alimenta o backend, não precisa reencaminhar).
const ENCAMINHAR = (process.env.ENCAMINHAR_WHATSAPP || 'false').toLowerCase() === 'true';
const NUMERO_DESTINO = process.env.NUMERO_DESTINO || '';

// Arquivo lido pelo backend Python.
const INBOX = path.join(__dirname, '..', 'data', 'espelho_inbox.jsonl');
fs.mkdirSync(path.dirname(INBOX), { recursive: true });

// =========================================================================

const client = new Client({
  authStrategy: new LocalAuth(), // salva a sessão (não pede QR toda vez)
  puppeteer: { args: ['--no-sandbox', '--disable-setuid-sandbox'] },
});

client.on('qr', (qr) => {
  console.log('Escaneie o QR Code com o WhatsApp do NÚMERO DEDICADO (que está nos grupos):');
  qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
  console.log('✅ Bot Espelho conectado!');
  if (GRUPOS_PERMITIDOS.length) {
    console.log('Monitorando grupos:', GRUPOS_PERMITIDOS.join(', '));
  } else {
    console.log('Monitorando TODOS os grupos (defina ESPELHO_GRUPOS no .env p/ filtrar).');
  }
  console.log('Gravando sinais de tendência em:', INBOX);
  if (ENCAMINHAR && NUMERO_DESTINO) {
    console.log('Reencaminhando também p/', NUMERO_DESTINO);
  }
});

function removerLinks(texto) {
  if (!texto) return '';
  const urlRegex = /(https?:\/\/[^\s]+)|(www\.[^\s]+)/g;
  return texto.replace(urlRegex, '[LINK REMOVIDO]').trim();
}

function gravarInbox(grupo, texto) {
  if (!texto || !texto.trim()) return;
  // Texto BRUTO (com link): o Python extrai só o nome do produto.
  const linha = JSON.stringify({ ts: Date.now(), group: grupo, text: texto });
  fs.appendFile(INBOX, linha + '\n', (err) => {
    if (err) console.error('Erro ao gravar inbox:', err.message);
  });
}

client.on('message', async (msg) => {
  try {
    const chat = await msg.getChat();
    if (!chat.isGroup) return;
    if (GRUPOS_PERMITIDOS.length > 0 && !GRUPOS_PERMITIDOS.includes(chat.name)) return;

    const preview = (msg.body || '').slice(0, 60).replace(/\n/g, ' ');
    console.log(`\n📩 ${chat.name}: ${preview}`);

    // (1) Sinal de tendência p/ o backend.
    gravarInbox(chat.name, msg.body || '');

    // (2) Reencaminho opcional (modelo antigo, desligado por padrão).
    if (ENCAMINHAR && NUMERO_DESTINO) {
      const textoLimpo = removerLinks(msg.body);
      if (msg.hasMedia) {
        const media = await msg.downloadMedia();
        if (media) await client.sendMessage(NUMERO_DESTINO, media, { caption: textoLimpo });
      } else if (textoLimpo) {
        await client.sendMessage(NUMERO_DESTINO, textoLimpo);
      }
    }
  } catch (error) {
    console.error('Erro ao processar mensagem:', error);
  }
});

client.initialize();

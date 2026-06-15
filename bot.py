import discord
from discord.ext import commands
import deepl
import os
from dotenv import load_dotenv
import re

# .env yükleme
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

# DeepL istemcisi
translator = deepl.Translator(DEEPL_API_KEY)

# Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# İzinli rol ID'si
ALLOWED_ROLE_ID = 1469669337051959377

# Dil-kanal eşleşmeleri
LANG_CHANNELS = {
    "TR": 1433122184808763504,
    "DE": 1433122214655426602,
    "IT": 1433128391053410515,
    "ES": 1433128352751030332,
    "PL": 1433128425475805235,
    "PT-PT": 1433122303851368478,
    "RO": 1433128235599921192,
    "HU": 1433128274472599622,
    "FR": 1433128206189461525,
    "EL": 1433128224128368760,
}

# İzin kontrolü için decorator
def has_permission():
    async def predicate(ctx):
        # Sunucu sahibi her zaman izinlidir
        if ctx.author.id == ctx.guild.owner_id:
            return True
        
        # Belirtilen role sahip mi kontrol et
        role = discord.utils.get(ctx.author.roles, id=ALLOWED_ROLE_ID)
        if role:
            return True
        
        # İzin yoksa hata mesajı gönder
        await ctx.send("❌ Bu komutu kullanma yetkiniz yok! (Permis rolü gerekli)")
        return False
    
    return commands.check(predicate)

class LineStructure:
    """Bir satırın tam yapısını tutar"""
    def __init__(self, original_line):
        self.original = original_line
        self.is_empty = len(original_line.strip()) == 0
        
        # Prefix'ler
        self.quote = ''
        self.header = ''
        self.list_indent = ''
        self.list_marker = ''
        
        # Discord öğeleri
        self.timestamps = []
        self.custom_emojis = []
        self.mentions = []
        self.links = []
        
        # Markdown formatları
        self.bold_italic_map = []  # (start_idx, end_idx, format_type, original_text)
        
        # Temiz metin
        self.clean_text = ''
        
        if not self.is_empty:
            self._parse()
    
    def _parse(self):
        """Satırı parse et"""
        text = self.original
        
        # 1. Quote prefix
        if text.startswith('> '):
            self.quote = '> '
            text = text[2:]
        
        # 2. Header prefix
        match = re.match(r'^(#{1,3})\s+', text)
        if match:
            self.header = match.group(0)
            text = text[len(match.group(0)):]
        
        # 3. List indent ve marker
        match = re.match(r'^(\s*)([-*+]|\d+\.)\s+', text)
        if match:
            self.list_indent = match.group(1)
            self.list_marker = match.group(2) + ' '
            text = text[len(match.group(0)):]
        
        # 4. Discord elementlerini çıkar
        # Timestamps
        for ts in re.finditer(r'<t:\d+:[tTdDfFR]>', text):
            self.timestamps.append(ts.group(0))
            text = text.replace(ts.group(0), ' ', 1)
        
        # Custom emojis
        for emoji in re.finditer(r'<a?:\w+:\d+>', text):
            self.custom_emojis.append(emoji.group(0))
            text = text.replace(emoji.group(0), ' ', 1)
        
        # Mentions
        for mention in re.finditer(r'@everyone|@here|<@[&!]?\d+>', text):
            self.mentions.append(mention.group(0))
            text = text.replace(mention.group(0), ' ', 1)
        
        # 5. Links - [text](url)
        for link in re.finditer(r'\[([^\]]+)\]\(([^\)]+)\)', text):
            self.links.append({
                'text': link.group(1),
                'url': link.group(2),
                'full': link.group(0)
            })
            text = text.replace(link.group(0), link.group(1), 1)
        
        # 6. Bold ve italic formatları kaydet
        # Önce konumları tespit et
        temp_text = text
        
        # Bold-italic (***text***)
        for match in re.finditer(r'\*\*\*(.+?)\*\*\*', temp_text):
            self.bold_italic_map.append({
                'text': match.group(1),
                'format': '***',
                'full': match.group(0)
            })
        
        # Bold (**text**)
        for match in re.finditer(r'(?<!\*)\*\*(.+?)\*\*(?!\*)', temp_text):
            # Bold-italic içinde değilse ekle
            if not any(m['full'] in match.group(0) or match.group(0) in m['full'] 
                      for m in self.bold_italic_map if m['format'] == '***'):
                self.bold_italic_map.append({
                    'text': match.group(1),
                    'format': '**',
                    'full': match.group(0)
                })
        
        # Italic (*text*)
        for match in re.finditer(r'(?<!\*)\*(.+?)\*(?!\*)', temp_text):
            # Bold veya bold-italic içinde değilse ekle
            if not any(match.group(0) in m['full'] or m['full'] in match.group(0)
                      for m in self.bold_italic_map):
                self.bold_italic_map.append({
                    'text': match.group(1),
                    'format': '*',
                    'full': match.group(0)
                })
        
        # 7. Markdown'ı temizle
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'(?<!\*)\*(.+?)\*(?!\*)', r'\1', text)
        text = re.sub(r'~~(.+?)~~', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        
        # Fazla boşlukları temizle
        text = ' '.join(text.split())
        
        self.clean_text = text
    
    def rebuild(self, translated_text):
        """Çevrilmiş metni formatla"""
        if self.is_empty:
            return ''
        
        result = translated_text.strip()
        
        # 1. Bold/italic formatlarını geri ekle
        # Her formatlı segmenti çevrilmiş metinde bulmaya çalış
        for fmt_info in self.bold_italic_map:
            original = fmt_info['text']
            # Orijinal metnin ilk kelimesini bul
            words = original.split()
            if words:
                # İlk 1-2 kelimeyi kullanarak formatı uygula
                search_pattern = r'\b' + re.escape(words[0]) + r'\b'
                if len(words) > 1:
                    # İkinci kelime de varsa, onu da dahil et
                    search_pattern = r'\b' + re.escape(words[0]) + r'\s+' + re.escape(words[1]) + r'\b'
                    replacement = fmt_info['format'] + words[0] + ' ' + words[1] + fmt_info['format']
                else:
                    replacement = fmt_info['format'] + words[0] + fmt_info['format']
                
                result = re.sub(search_pattern, replacement, result, count=1, flags=re.IGNORECASE)
        
        # 2. Links'i geri ekle
        for link in self.links:
            # Link metnini çevrilmiş metinde bul ve linki geri ekle
            link_text = link['text']
            words = link_text.split()
            if words:
                # İlk kelimeyi bul ve link yap
                pattern = r'\b' + re.escape(words[0]) + r'\b'
                replacement = f"[{words[0]}]({link['url']})"
                result = re.sub(pattern, replacement, result, count=1, flags=re.IGNORECASE)
        
        # 3. Discord elementlerini ekle (sona)
        for ts in self.timestamps:
            result += ' ' + ts
        
        for emoji in self.custom_emojis:
            result += ' ' + emoji
        
        for mention in self.mentions:
            result += ' ' + mention
        
        # 4. Prefix'leri ekle
        if self.list_marker:
            result = self.list_indent + self.list_marker + result
        
        if self.header:
            result = self.header + result
        
        if self.quote:
            result = self.quote + result
        
        return result

def translate_message(text, target_lang):
    """Mesajı çevir, her satırı ayrı işle"""
    lines = text.split('\n')
    structures = []
    translatable_texts = []
    
    # 1. Her satırı parse et
    for line in lines:
        struct = LineStructure(line)
        structures.append(struct)
        if not struct.is_empty and struct.clean_text:
            translatable_texts.append(struct.clean_text)
    
    # 2. Boş olmayan satırları çevir
    translated_texts = []
    for clean_text in translatable_texts:
        try:
            result = translator.translate_text(
                clean_text,
                target_lang=target_lang,
                preserve_formatting=False  # Manuel kontrol için False
            )
            translated_texts.append(result.text)
        except Exception as e:
            print(f"Translation error: {e}")
            translated_texts.append(clean_text)
    
    # 3. Çevrilmiş metinleri yapıyla birleştir
    result_lines = []
    translated_idx = 0
    
    for struct in structures:
        if struct.is_empty:
            result_lines.append('')
        elif struct.clean_text:
            translated = translated_texts[translated_idx]
            rebuilt = struct.rebuild(translated)
            result_lines.append(rebuilt)
            translated_idx += 1
        else:
            result_lines.append(struct.original)
    
    return '\n'.join(result_lines)

def split_message(text, limit=1900):
    """Mesajları böl"""
    if len(text) <= limit:
        return [text]
    
    lines = text.split('\n')
    chunks = []
    current = []
    current_len = 0
    
    for line in lines:
        line_len = len(line) + 1
        
        if line_len > limit:
            if current:
                chunks.append('\n'.join(current))
                current = []
                current_len = 0
            chunks.append(line)
            continue
        
        if current_len + line_len > limit:
            if current:
                chunks.append('\n'.join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len
    
    if current:
        chunks.append('\n'.join(current))
    
    return chunks

@bot.event
async def on_ready():
    print(f"{bot.user} is ready!")

async def get_message_text(ctx):
    content = ctx.message.content.replace(f"{ctx.prefix}{ctx.invoked_with}", "").strip()
    
    parts = content.split(None, 1)
    if parts and parts[0] in LANG_CHANNELS:
        text = parts[1] if len(parts) > 1 else ""
    else:
        text = content
    
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.filename.endswith(".txt"):
            file_content = await attachment.read()
            file_text = file_content.decode("utf-8").strip()
            text = (text + "\n" + file_text).strip()
        else:
            await ctx.send("⚠️ Only txt files supported")
            return ""

    return text.strip()

@bot.command()
@has_permission()
async def announce(ctx):
    message_text = await get_message_text(ctx)
    if not message_text:
        await ctx.send("❌ Please provide a message or txt file")
        return

    await ctx.send("🔄 Translating and sending...")

    success = 0
    for lang, channel_id in LANG_CHANNELS.items():
        try:
            translated = translate_message(message_text, lang)
            
            channel = bot.get_channel(channel_id)
            if channel:
                for chunk in split_message(translated):
                    await channel.send(chunk)
                success += 1
        except Exception as e:
            await ctx.send(f"⚠️ {lang} failed: {e}")
            print(f"Error in {lang}: {e}")

    await ctx.send(f"✅ Sent to {success}/{len(LANG_CHANNELS)} languages")

@bot.command()
@has_permission()
async def announce_lang(ctx, lang):
    if lang not in LANG_CHANNELS:
        await ctx.send(f"❌ Invalid: {', '.join(LANG_CHANNELS.keys())}")
        return

    message_text = await get_message_text(ctx)
    if not message_text:
        await ctx.send("❌ Please provide a message or txt file")
        return

    await ctx.send(f"🔄 Translating to {lang}...")

    try:
        translated = translate_message(message_text, lang)
        
        channel = bot.get_channel(LANG_CHANNELS[lang])
        if channel:
            for chunk in split_message(translated):
                await channel.send(chunk)
        
        await ctx.send(f"✅ Sent to {lang}")
    except Exception as e:
        await ctx.send(f"⚠️ Failed: {e}")
        print(f"Error: {e}")

@bot.command()
@has_permission()
async def test(ctx, lang):
    """Test translation locally"""
    if lang not in LANG_CHANNELS:
        await ctx.send(f"❌ Invalid: {', '.join(LANG_CHANNELS.keys())}")
        return

    message_text = await get_message_text(ctx)
    if not message_text:
        await ctx.send("❌ Provide message or txt file")
        return

    await ctx.send(f"🧪 Testing {lang}...")

    try:
        translated = translate_message(message_text, lang)
        
        for chunk in split_message(translated, 1800):
            await ctx.send(f"```\n{chunk}\n```")
        
        await ctx.send(f"✅ Test done")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

bot.run(DISCORD_TOKEN)
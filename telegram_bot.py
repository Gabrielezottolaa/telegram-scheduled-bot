from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import asyncio
import os

WAITING_DATE, WAITING_TIME, WAITING_TEXT, WAITING_MORE_TEXT, WAITING_INTERVAL = range(5)
user_data_store = {}

class ScheduledMessageBot:
    def __init__(self):
        self.scheduled_tasks = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Benvenuto! Usa /giorno per programmare l'invio di messaggi a intervalli."
        )

    async def giorno_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_data_store[user_id] = {'text_parts': []}
        await update.message.reply_text(
            "📅 Inserisci la data nel formato GG/MM/AA (esempio: 22/10/25):"
        )
        return WAITING_DATE

    async def receive_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        date_text = update.message.text.strip()
        try:
            date_obj = datetime.strptime(date_text, "%d/%m/%y")
            user_data_store[user_id]['date'] = date_obj.date()
            await update.message.reply_text(
                f"✅ Data impostata: {date_obj.strftime('%d/%m/%Y')}\n\n"
                "🕐 Ora inserisci l'ora nel formato HH:MM (esempio: 14:30):"
            )
            return WAITING_TIME
        except ValueError:
            await update.message.reply_text(
                "❌ Formato data non valido. Usa il formato GG/MM/AA (esempio: 22/10/25):"
            )
            return WAITING_DATE

    async def receive_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        time_text = update.message.text.strip()
        try:
            time_obj = datetime.strptime(time_text, "%H:%M").time()
            user_data_store[user_id]['time'] = time_obj
            await update.message.reply_text(
                f"✅ Ora impostata: {time_obj.strftime('%H:%M')}\n\n"
                "📝 Ora invia il testo da programmare:"
            )
            return WAITING_TEXT
        except ValueError:
            await update.message.reply_text(
                "❌ Formato ora non valido. Usa il formato HH:MM (esempio: 14:30):"
            )
            return WAITING_TIME

    async def receive_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        user_data_store[user_id]['text_parts'].append(text)
        await update.message.reply_text(
            "📨 C'è altro testo da aggiungere? Invialo ora, oppure scrivi 'basta' per terminare."
        )
        return WAITING_MORE_TEXT

    async def receive_more_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        if text.lower().strip() == 'basta':
            full_text = '\n'.join(user_data_store[user_id]['text_parts'])
            user_data_store[user_id]['full_text'] = full_text
            await update.message.reply_text(
                f"✅ Testo completo ricevuto ({len(full_text)} caratteri).\n\n"
                "⏱ Ogni quanti minuti vuoi inviare i messaggi? (inserisci solo il numero):"
            )
            return WAITING_INTERVAL
        else:
            user_data_store[user_id]['text_parts'].append(text)
            await update.message.reply_text(
                "📨 Testo aggiunto. C'è altro? Invialo ora, oppure scrivi 'basta' per terminare."
            )
            return WAITING_MORE_TEXT

    async def receive_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            interval_minutes = int(update.message.text.strip())
            if interval_minutes <= 0:
                await update.message.reply_text(
                    "❌ L'intervallo deve essere un numero positivo. Riprova:"
                )
                return WAITING_INTERVAL
            
            user_data_store[user_id]['interval'] = interval_minutes
            full_text = user_data_store[user_id]['full_text']
            chunks = [full_text[i:i+360] for i in range(0, len(full_text), 360)]
            start_date = user_data_store[user_id]['date']
            start_time = user_data_store[user_id]['time']
            start_datetime = datetime.combine(start_date, start_time)
            
            summary = (
                f"✅ Programmazione completata!\n\n"
                f"📅 Data: {start_date.strftime('%d/%m/%Y')}\n"
                f"🕐 Ora inizio: {start_time.strftime('%H:%M')}\n"
                f"⏱ Intervallo: {interval_minutes} minuti\n"
                f"📝 Numero di messaggi: {len(chunks)}\n"
                f"📊 Caratteri totali: {len(full_text)}\n\n"
                f"I messaggi verranno inviati a partire dal {start_datetime.strftime('%d/%m/%Y alle %H:%M')}"
            )
            await update.message.reply_text(summary)
            
            asyncio.create_task(
                self.schedule_messages_async(
                    context.bot, user_id, chunks, start_datetime, interval_minutes
                )
            )
            del user_data_store[user_id]
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido di minuti:")
            return WAITING_INTERVAL

    async def schedule_messages_async(self, bot, user_id, chunks, start_datetime, interval_minutes):
        print(f"📅 Programmazione di {len(chunks)} messaggi per l'utente {user_id}")
        for i, chunk in enumerate(chunks):
            send_time = start_datetime + timedelta(minutes=i * interval_minutes)
            delay = (send_time - datetime.now()).total_seconds()
            if delay > 0:
                print(f"⏰ Messaggio {i+1}/{len(chunks)} programmato per {send_time.strftime('%d/%m/%Y %H:%M:%S')}")
                await asyncio.sleep(delay)
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"📬 Messaggio {i + 1}/{len(chunks)}\n\n{chunk}"
                    )
                    print(f"✅ Messaggio {i+1}/{len(chunks)} inviato a {user_id}")
                except Exception as e:
                    print(f"❌ Errore nell'invio del messaggio {i+1} a {user_id}: {e}")
            else:
                print(f"⚠️ Il messaggio {i+1} è programmato per un orario passato e verrà saltato.")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in user_data_store:
            del user_data_store[user_id]
        await update.message.reply_text("❌ Operazione annullata. Usa /giorno per ricominciare.")
        return ConversationHandler.END

def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8314030259:AAH4Y4CW-fP9s07jnM3wytKdb5aKd-PF_-w")
    bot = ScheduledMessageBot()
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('giorno', bot.giorno_command)],
        states={
            WAITING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_date)],
            WAITING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_time)],
            WAITING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_text)],
            WAITING_MORE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_more_text)],
            WAITING_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_interval)],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    
    application.add_handler(CommandHandler('start', bot.start))
    application.add_handler(conv_handler)
    
    print("🤖 Bot avviato su Render...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

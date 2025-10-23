import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import asyncio

# Stati per la conversazione
WAITING_DATE, WAITING_TIME, WAITING_TEXT, WAITING_MORE_TEXT, WAITING_INTERVAL = range(5)

# Dizionario per memorizzare i dati degli utenti
user_data_store = {}

class ScheduledMessageBot:
    def __init__(self):
        self.scheduled_tasks = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando di benvenuto"""
        await update.message.reply_text(
            "🤖 Benvenuto! Usa /giorno per programmare l'invio di messaggi a intervalli."
        )

    async def giorno_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inizia il processo di configurazione"""
        user_id = update.effective_user.id
        user_data_store[user_id] = {'text_parts': []}
        
        await update.message.reply_text(
            "📅 Inserisci la data nel formato GG/MM/AA (esempio: 22/10/25):"
        )
        return WAITING_DATE

    async def receive_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Riceve e valida la data"""
        user_id = update.effective_user.id
        date_text = update.message.text.strip()
        
        try:
            # Parsing della data
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
        """Riceve e valida l'ora"""
        user_id = update.effective_user.id
        time_text = update.message.text.strip()
        
        try:
            # Parsing dell'ora
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
        """Riceve il primo pezzo di testo"""
        user_id = update.effective_user.id
        text = update.message.text
        
        user_data_store[user_id]['text_parts'].append(text)
        
        await update.message.reply_text(
            "📨 C'è altro testo da aggiungere? Invialo ora, oppure scrivi 'basta' per terminare."
        )
        return WAITING_MORE_TEXT

    async def receive_more_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Riceve testo aggiuntivo o termina la raccolta"""
        user_id = update.effective_user.id
        text = update.message.text
        
        if text.lower().strip() == 'basta':
            # Combina tutto il testo
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
        """Riceve l'intervallo e programma i messaggi"""
        user_id = update.effective_user.id
        
        try:
            interval_minutes = int(update.message.text.strip())
            
            if interval_minutes <= 0:
                await update.message.reply_text(
                    "❌ L'intervallo deve essere un numero positivo. Riprova:"
                )
                return WAITING_INTERVAL
            
            user_data_store[user_id]['interval'] = interval_minutes
            
            # Divide il testo in chunks di 360 caratteri
            full_text = user_data_store[user_id]['full_text']
            chunks = [full_text[i:i+400] for i in range(0, len(full_text), 400)]
            
            # Calcola la data e ora di inizio
            start_date = user_data_store[user_id]['date']
            start_time = user_data_store[user_id]['time']
            start_datetime = datetime.combine(start_date, start_time)
            
            # Mostra riepilogo
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
            
            # Programma l'invio dei messaggi
            await self.schedule_messages(
                context, 
                user_id, 
                chunks, 
                start_datetime, 
                interval_minutes
            )
            
            # Pulisce i dati dell'utente
            del user_data_store[user_id]
            
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "❌ Inserisci un numero valido di minuti:"
            )
            return WAITING_INTERVAL

    async def schedule_messages(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                                chunks: list, start_datetime: datetime, interval_minutes: int):
        """Programma l'invio dei messaggi"""
        for i, chunk in enumerate(chunks):
            send_time = start_datetime + timedelta(minutes=i * interval_minutes)
            
            # Calcola il ritardo in secondi
            delay = (send_time - datetime.now()).total_seconds()
            
            if delay > 0:
                # Programma il messaggio
                context.application.job_queue.run_once(
                    self.send_scheduled_message,
                    delay,
                    data={'user_id': user_id, 'message': chunk, 'index': i + 1, 'total': len(chunks)},
                    name=f"msg_{user_id}_{i}"
                )
            else:
                print(f"⚠️ Il messaggio {i+1} è programmato per un orario passato e verrà saltato.")

    async def send_scheduled_message(self, context: ContextTypes.DEFAULT_TYPE):
        """Invia il messaggio programmato"""
        job_data = context.job.data
        user_id = job_data['user_id']
        message = job_data['message']
        index = job_data['index']
        total = job_data['total']
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📬 Messaggio {index}/{total}\n\n{message}"
            )
            print(f"✅ Messaggio {index}/{total} inviato a {user_id}")
        except Exception as e:
            print(f"❌ Errore nell'invio del messaggio a {user_id}: {e}")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Annulla la conversazione"""
        user_id = update.effective_user.id
        if user_id in user_data_store:
            del user_data_store[user_id]
        
        await update.message.reply_text(
            "❌ Operazione annullata. Usa /giorno per ricominciare."
        )
        return ConversationHandler.END

def main():
    """Avvia il bot"""
    TOKEN = "8314030259:AAH4Y4CW-fP9s07jnM3wytKdb5aKd-PF_-w"
    
    bot = ScheduledMessageBot()
    
    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()
    
    # Conversation handler
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
    
    # Avvia il bot
    print("🤖 Bot avviato e in ascolto...")
    application.run_polling()

if __name__ == '__main__':
    main()

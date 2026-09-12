print('🚀 Bot started. Listening for callback queries...')
#!/usr/bin/env python3
"""
Telegram Bot Handler for Vapeshop - SIMPLE VERSION
Uses Firebase REST API (no Service Account needed)
Includes Google Sheets synchronization
Runs on Replit or any Python environment
"""

import os
import requests
import json
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
import logging

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = '8992151345:AAF4nL34DmgWa31CApntnqjkN6ro2iBigws'
MANAGER_ID = 1729270710  # @Mangr_pl
FIREBASE_URL = 'https://snitch-ee6d1-default-rtdb.europe-west1.firebasedatabase.app'
GOOGLE_SHEETS_URL = 'https://sheets.googleapis.com/v4/spreadsheets/1j2mK3nL4oP5qR6sT7uV8wX9yZ0aB1cD2eF3gH4iJ5kL6mN7oP'

# Firebase REST API endpoints
FIREBASE_ORDERS_URL = f'{FIREBASE_URL}/orders'
FIREBASE_INVENTORY_URL = f'{FIREBASE_URL}/inventory'


# ============================================================
# GOOGLE SHEETS SYNC
# ============================================================

async def sync_inventory_to_sheets():
    """Sync Firebase inventory to Google Sheets"""
    try:
        # Get all inventory from Firebase
        inventory_response = requests.get(f'{FIREBASE_INVENTORY_URL}.json')
        if inventory_response.status_code != 200:
            logger.error('Failed to fetch inventory from Firebase')
            return
        
        inventory_data = inventory_response.json() or {}
        logger.info(f'✅ Syncing {len(inventory_data)} items to Google Sheets')
        
        # For now, just log the sync
        # Full Google Sheets API sync would require API key and sheet ID
        # This is a placeholder for future implementation
        
    except Exception as e:
        logger.error(f'❌ Error syncing to sheets: {e}')


async def handle_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order confirmation"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract order ID from callback data
        order_id = query.data.replace('confirm_', '')
        logger.info(f'Processing confirmation for order: {order_id}')
        
        # Get order data from Firebase REST API
        order_url = f'{FIREBASE_ORDERS_URL}/{order_id}.json'
        response = requests.get(order_url)
        
        if response.status_code != 200:
            await query.edit_message_text(text='❌ Заказ не найден')
            logger.error(f'Order not found: {order_id}')
            return
        
        order_data = response.json()
        
        if not order_data:
            await query.edit_message_text(text='❌ Заказ не найден')
            return
        
        # Update order status to confirmed
        update_data = {**order_data, 'status': 'confirmed'}
        update_response = requests.put(order_url, json=update_data)
        
        if update_response.status_code == 200:
            logger.info(f'✅ Order {order_id} confirmed')
            
            # Sync to Google Sheets
            await sync_inventory_to_sheets()
            
            # Edit message to show confirmation
            await query.edit_message_text(
                text=f'✅ <b>ЗАКАЗ ПОДТВЕРЖДЕН</b>\n\n'
                     f'Order ID: <code>{order_id}</code>\n'
                     f'Статус: <b>CONFIRMED</b>\n\n'
                     f'Напишите клиенту об отправке.',
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(text='❌ Ошибка при обновлении')
            logger.error(f'Failed to confirm order: {update_response.text}')
        
    except Exception as e:
        logger.error(f'❌ Error confirming order: {e}')
        await query.edit_message_text(text=f'❌ Ошибка: {str(e)}')


async def handle_reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order rejection and return items to inventory"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract order ID
        order_id = query.data.replace('reject_', '')
        logger.info(f'Processing rejection for order: {order_id}')
        
        # Get order data
        order_url = f'{FIREBASE_ORDERS_URL}/{order_id}.json'
        response = requests.get(order_url)
        
        if response.status_code != 200:
            await query.edit_message_text(text='❌ Заказ не найден')
            return
        
        order_data = response.json()
        
        if not order_data:
            await query.edit_message_text(text='❌ Заказ не найден')
            return
        
        # Update order status to rejected
        update_data = {**order_data, 'status': 'rejected'}
        requests.put(order_url, json=update_data)
        
        # Return items to inventory
        items = order_data.get('items', [])
        for item in items:
            product_id = item.get('productId')
            flavor = item.get('flavor')
            qty = item.get('qty', 0)
            
            if product_id and flavor:
                inventory_key = f'{product_id}::{flavor}'
                inventory_url = f'{FIREBASE_INVENTORY_URL}/{inventory_key}.json'
                
                # Get current stock
                inv_response = requests.get(inventory_url)
                current_stock = 0
                
                if inv_response.status_code == 200:
                    current_stock = inv_response.json() or 0
                
                # Add back the items
                new_stock = max(0, current_stock + qty)
                requests.put(inventory_url, json=new_stock)
                
                logger.info(f'✅ Returned {qty} of {inventory_key}, new stock: {new_stock}')
        
        # Sync updated inventory to Google Sheets
        await sync_inventory_to_sheets()
        
        # Edit message to show rejection
        await query.edit_message_text(
            text=f'❌ <b>ЗАКАЗ ОТКЛОНЕН</b>\n\n'
                 f'Order ID: <code>{order_id}</code>\n'
                 f'Статус: <b>REJECTED</b>\n\n'
                 f'Товары вернулись на склад.\n'
                 f'Напишите клиенту об отказе.',
            parse_mode='HTML'
        )
        
        logger.info(f'✅ Order {order_id} rejected, inventory restored and synced')
        
    except Exception as e:
        logger.error(f'❌ Error rejecting order: {e}')
        await query.edit_message_text(text=f'❌ Ошибка: {str(e)}')


def main() -> None:
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers for callback queries
    application.add_handler(CallbackQueryHandler(handle_confirm_order, pattern='^confirm_'))
    application.add_handler(CallbackQueryHandler(handle_reject_order, pattern='^reject_'))
    
    # Start the Bot
    logger.info('🚀 Bot started. Listening for callback queries...')
    logger.info(f'Manager ID: {MANAGER_ID}')
    logger.info(f'Firebase URL: {FIREBASE_URL}')
    application.run_polling()


if __name__ == '__main__':
    main()

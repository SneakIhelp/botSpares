import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import pyodbc
import re

API_TOKEN = '6032353284:AAHf53QoE8Uj4nJ_H3PGuBFaxYQMvwDll20'
bot = telebot.TeleBot(API_TOKEN)
model_answ = {}
headlights_answ = {}

bd = pyodbc.connect('Driver={SQL Server};'
                    'Server=DESKTOP\\SQLEXPRESS;'
                    'Database=bottg;'
                    'Trusted_Connection=yes;')
cursor = bd.cursor()

cursor.execute('SELECT * FROM dbo.spares')

columns = [column[0] for column in cursor.description]
rows = cursor.fetchall()
products = []
models = []
models_ind = []
num_row = 0

for row in rows:
    products.append({})
    for i in range(len(columns)):
        products[num_row][columns[i]] = row[i]
    num_row += 1

cart = {}


@bot.message_handler(commands=['start'])
def send_welcome(message):
    cursor.execute('SELECT * FROM dbo.models')

    global models, models_ind
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    keyboard = InlineKeyboardMarkup()
    for row in rows:
        for i in range(1, len(columns), 2):
            models.append(row[i])
            button = InlineKeyboardButton(text=row[i], callback_data=row[i])
            keyboard.add(button)
        for i in range(0, len(columns), 2):
            models_ind.append(row[i])

    msg = bot.reply_to(message, "Добро пожаловать! Выберите модель марки машины BMW для покупки.",
                       reply_markup=keyboard)

    user_id = message.from_user.id
    if user_id in cart:
        del cart[user_id]
    bot.register_next_step_handler(msg, choose_products)


def choose_products(message):
    global cart
    model_answ[message.chat.id] = message.text
    user_id = message.from_user.id
    if not cart.get(user_id):
        show_products(message)
        bot.send_message(chat_id=message.chat.id, text="Чтобы перейти к корзине, напишите, '/cart'!")
        bot.register_next_step_handler(message, checkout)


@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call: CallbackQuery):
    user_id = call.from_user.id
    product_id = ""
    if call.data not in models:
        if call.data != "user_data":
            product_id = int(call.data[call.data.find("_") + 1:])
        if user_id not in cart:
            cart[user_id] = {}
        if call.data.startswith("add_"):
            if product_id in cart[user_id]:
                cart[user_id][product_id] += 1
            else:
                cart[user_id][product_id] = 1
            update_button_text(call.message.chat.id, call.message.message_id, product_id)
        elif call.data.startswith("plus_"):
            if product_id in cart[user_id]:
                cart[user_id][product_id] += 1
            else:
                cart[user_id][product_id] = 1
            update_button_text(call.message.chat.id, call.message.message_id, product_id)
        elif call.data.startswith("minus_"):
            if product_id in cart[user_id]:
                if product_id not in cart[user_id]:
                    bot.answer_callback_query(call.id, "Чтобы уменьшать количество штук нужно добавить товар в "
                                                       "корзину!")
                else:
                    cart[user_id][product_id] -= 1
                    update_button_text(call.message.chat.id, call.message.message_id, product_id)
                if cart[user_id][product_id] == 0:
                    del cart[user_id][product_id]
                    update_button_text(call.message.chat.id, call.message.message_id, product_id)
        elif call.data == "user_data":
            username(call.message)
        else:
            bot.answer_callback_query(call.id, "Invalid callback data")
    else:
        global model
        model = call.data
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Вы выбрали BMW {call.data}. Выберите фары для этой модели из списка.")
        choose_products(call.message)


def show_products(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Выберите продукты:")
    for product in products:
        if models_ind[models.index(model)] == product['id_spares']:
            message_text = f"{product['name_spares']} - ₽{product['price_spares']}"
            quantity = 0
            if message.chat.id in cart and product["id_spares"] in cart[message.chat.id]:
                quantity = cart[message.chat.id][product["id_spares"]]
            buttons = [
                InlineKeyboardButton(text="-", callback_data=f"minus_{product['id_spares']}"),
                InlineKeyboardButton(text=str(quantity), callback_data=f"quantity_{product['id_spares']}"),
                InlineKeyboardButton(text="+", callback_data=f"plus_{product['id_spares']}")
            ]
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="Добавить в корзину", callback_data=f"add_{product['id_spares']}")], buttons])
            bot.send_photo(chat_id, photo=open('photo_for_prod.jpg', 'rb'), caption=message_text, reply_markup=reply_markup)


def update_button_text(chat_id, message_id, product_id):
    button_text = "Добавить в корзину"
    if product_id in cart.get(chat_id, {}):
        button_text = "Добавлено в корзину"
    button = InlineKeyboardButton(text=button_text, callback_data=f"add_{product_id}")
    quantity = cart[chat_id].get(product_id, 0)
    buttons = [
        InlineKeyboardButton(text="-", callback_data=f"minus_{product_id}"),
        InlineKeyboardButton(text=str(quantity), callback_data=f"quantity_{product_id}"),
        InlineKeyboardButton(text="+", callback_data=f"plus_{product_id}")
    ]
    product_buttons = [[button], buttons]
    reply_markup = InlineKeyboardMarkup(product_buttons)
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)


def check_correct_number(number):
    return re.match(r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$', number)


def get_id(table):
    cursor.execute(f'SELECT * FROM dbo.{table}')

    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    num_row = 0

    for row in rows:
        products.append({})
        for i in range(len(columns)):
            products[num_row][columns[i]] = row[i]
        num_row += 1
    return num_row + 1


@bot.message_handler(commands=['cart'])
def checkout(message):
    user_id = message.from_user.id
    if user_id not in cart or not cart[user_id]:
        bot.send_message(chat_id=message.chat.id, text="Ваша корзина пуста.")
    else:
        total_price = 0
        products_text = []
        to_database_product = -1
        to_database_quantity = -1
        for product_id in cart[user_id]:
            product = next((p for p in products if p["id_spares"] == product_id), None)
            if product:
                quantity = cart[user_id].get(product_id, 0)
                product_text = f"{product['name_spares']} - ₽{product['price_spares']} - {quantity} шт."
                products_text.append(product_text)
                total_price += int(product["price_spares"]) * quantity
                to_database_product = product_id
                to_database_quantity = quantity

        global id_cart
        id_cart = get_id("shopping_cart")
        cursor.execute("INSERT INTO shopping_cart (id_shopping_cart, id_spares, quantity, sum) VALUES (?, ?, ?, ?)",
                       id_cart, to_database_product, to_database_quantity, total_price)
        bd.commit()

        message_text = "Ваша корзина:\n\n"
        message_text += "\n".join(products_text)
        message_text += f"\n\nИтого: ₽{total_price}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="Оформить заказ", callback_data="user_data")]])
        bot.send_message(chat_id=message.chat.id, text=message_text, reply_markup=reply_markup)


def username(message):
    msg = bot.reply_to(message, "Пожалуйста, предоставьте выше ФИО. Данные вводите именно в таком порядке и через пробел:")
    bot.register_next_step_handler(msg, process_name_step)


def process_name_step(message):
    name = message.text
    msg = bot.reply_to(message, "Теперь, введите ваш номер телефона в формате +79XXXXXXXXX:")
    bot.register_next_step_handler(msg, process_phone_step, name)


def process_phone_step(message, name):
    phone = message.text
    msg = bot.reply_to(message, "Введите адрес доставки:")
    bot.register_next_step_handler(msg, process_address_step, name, phone)


def process_address_step(message, name, phone):
    address = message.text
    msg = bot.reply_to(message, "Введите время доставки (формат ввода: 10:00 - 14:00):")
    bot.register_next_step_handler(msg, process_delivery_time_step, name, phone, address)


def process_delivery_time_step(message, name, phone, address):
    delivery_time = message.text
    nasupat = name.split()
    cursor.execute("INSERT INTO client (id_client, tele_id, name_client, surname_client, patronymic_client, number_client, address_client) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (get_id("client"), str(message.chat.id), nasupat[1], nasupat[0], nasupat[2], str(phone), address))
    bd.commit()
    cursor.execute("INSERT INTO delivery (id_delivery, id_client, id_shopping_cart) VALUES (?, ?, ?)",
                   (get_id("delivery"), get_id("client") - 1, id_cart))
    bd.commit()
    bot.send_message(message.chat.id, f"Спасибо, {name}! Скоро с вами свяжется администратор для подтверждения заказа.")

    bot.send_message(message.chat.id,
                     f"Заказ подтвержден! Ваш заказ будет доставлен курьером с {delivery_time}. Оплата при получении "
                     f"заказа.")


bot.polling(none_stop=True)

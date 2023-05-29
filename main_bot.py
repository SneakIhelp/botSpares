import time
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import pyodbc
import io
import base64
from PIL import Image

API_TOKEN = '6032353284:AAHf53QoE8Uj4nJ_H3PGuBFaxYQMvwDll20'
bot = telebot.TeleBot(API_TOKEN)
model_answ = {}
headlights_answ = {}

bd = pyodbc.connect('Driver={SQL Server};'
                    'Server=DESKTOP-T5QI3N7\\SQLEXPRESS;'
                    'Database=bottg;'
                    'Trusted_Connection=yes;')
cursor = bd.cursor()

cursor.execute('SELECT * FROM dbo.spares')
columns = [column[0] for column in cursor.description]
rows = cursor.fetchall()
products = []
num_row = 0
for row in rows:
    products.append({})
    for i in range(len(columns)):
        products[num_row][columns[i]] = row[i]
    num_row += 1

users = {}
current_state = {}
num_states = {}
cart = {}


@bot.message_handler(commands=['start'])
def send_welcome(message):
    cursor.execute('SELECT * FROM dbo.models')

    global models, models_ind
    models, models_ind = [], []
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
    bot.register_next_step_handler(msg, choose_products)


def choose_products(message):
    global cart
    model_answ[message.chat.id] = message.text
    user_id = message.from_user.id
    if not cart.get(user_id) and not flag:
        show_categories(message)
        bot.register_next_step_handler(message, checkout)


@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call: CallbackQuery):
    if call.data == "/cart" or call.data == "/start":
        return
    global delivery_day, num_states, user_id, flag
    flag = 0
    user_id = call.from_user.id
    if user_id not in num_states:
        num_states[user_id] = 0
        current_state[user_id] = 0
    days_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    product_id = ""
    if call.data not in models:
        if call.data not in days_week:
            if not call.data.startswith("category_"):
                if call.data not in ["time_14:30 - 17:30", "time_10:00 - 14:00", "time_18:00 - 22:00"]:
                    if call.data != "user_data" and call.data != "back_to_models" and call.data != "back_to_cat" and call.data != "clear_cart":
                        product_id = int(call.data[call.data.find("_") + 1:])
                    if user_id not in cart:
                        cart[user_id] = {}
                    if call.data.startswith("add_"):
                        if product_id in cart[user_id]:
                            cart[user_id][product_id] += 1
                        else:
                            cart[user_id][product_id] = 1
                        update_button_text(call.message.chat.id, call.message.message_id, product_id)
                    elif call.data == "clear_cart":
                        del cart[user_id]
                        num_states[user_id] = 0
                        flag = 1
                        current_state[user_id] = 1
                        bot.answer_callback_query(call.id, "Корзина очищена.")
                    elif call.data.startswith("plus_"):
                        if product_id in cart[user_id]:
                            cart[user_id][product_id] += 1
                        else:
                            cart[user_id][product_id] = 1
                        update_button_text(call.message.chat.id, call.message.message_id, product_id)
                    elif call.data.startswith("minus_"):
                        if product_id in cart[user_id]:
                            if product_id not in cart[user_id]:
                                bot.answer_callback_query(call.id,
                                                          "Чтобы уменьшать количество штук нужно добавить товар в "
                                                          "корзину!")
                            else:
                                cart[user_id][product_id] -= 1
                                update_button_text(call.message.chat.id, call.message.message_id, product_id)
                            if user_id in cart and cart[user_id][product_id] == 0:
                                del cart[user_id][product_id]
                                update_button_text(call.message.chat.id, call.message.message_id, product_id)
                    elif call.data == "user_data":
                        username(call.message)
                    elif call.data == "back_to_models":
                        num_states[user_id] += 1
                        send_welcome(call.message)
                    elif call.data == "back_to_cat":
                        show_categories(call.message)
                    else:
                        bot.answer_callback_query(call.id, "Invalid callback data")

                else:
                    delivery_time = call.data.split("_")[-1]
                    process_delivery_time_step(choose_day_msg, client_name, client_phone, address, delivery_day,
                                               delivery_time)
            else:
                category = call.data.split("_")[1]
                show_products(call.message, category)
        else:
            delivery_day = call.data
            process_delivery_day_step(choose_day_msg)
    else:
        global model
        model = call.data
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Вы выбрали BMW {call.data}. Выберите деталь для этой модели из списка.")
        choose_products(call.message)


def show_categories(message):
    if message.text == "/cart" or message.text == "/start":
        return
    global categories
    chat_id = message.chat.id
    categories_temp = set()

    cursor.execute('SELECT * FROM dbo.spares')
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    products = []
    num_row = 0
    for row in rows:
        products.append({})
        for i in range(len(columns)):
            products[num_row][columns[i]] = row[i]
        num_row += 1

    for product in products:
        if models_ind[models.index(model)] == product['id_model']:
            categories_temp.add(product['category'])
    keyboard = InlineKeyboardMarkup()
    categories = list(categories_temp)
    for category in categories:
        button = InlineKeyboardButton(text=category, callback_data=f"category_{category}")
        keyboard.add(button)
    bot.send_message(chat_id, "Выберите категорию продуктов:", reply_markup=keyboard)
    bot.send_message(chat_id, "Вернуться назад к моделям:", reply_markup=InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Назад", callback_data=f"back_to_models")]]))
    bot.send_message(chat_id=message.chat.id, text="Чтобы перейти к корзине, напишите, '/cart'!")


def get_photo(row_id):
    sql_query = f"SELECT ImageData FROM spares WHERE id_spares = ?"
    cursor = bd.cursor()
    cursor.execute(sql_query, (row_id,))
    result = cursor.fetchone()
    try:
        photo_data = bytes(result[0])
        image = Image.open(io.BytesIO(photo_data))
    except:
        photo_data = bytes(result[0])
        decoded_data = base64.b64decode(photo_data)
        image = Image.open(io.BytesIO(decoded_data))

    return image


def show_products(message, category):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Выберите продукты:")

    for product in products:
        if models_ind[models.index(model)] == product['id_model'] and product['category'] == category:
            message_text = f"{product['name_spares']} - ₽{product['price_spares']}"
            quantity = 0
            if message.chat.id in cart and product["id_spares"] in cart[message.chat.id]:
                quantity = cart[message.chat.id][product["id_spares"]]
            buttons = [
                InlineKeyboardButton(text="-", callback_data=f"minus_{product['id_spares']}"),
                InlineKeyboardButton(text=str(quantity), callback_data=f"quantity_{product['id_spares']}"),
                InlineKeyboardButton(text="+", callback_data=f"plus_{product['id_spares']}")
            ]
            if quantity == 0:
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="Добавить в корзину", callback_data=f"add_{product['id_spares']}")],
                     buttons])
            else:
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="Добавлено в корзину", callback_data=f"add_{product['id_spares']}")],
                     buttons])
            image = get_photo(int(product['id_spares']))
            with io.BytesIO() as image_buffer:
                image.save(image_buffer, format='JPEG')
                image_buffer.seek(0)
                with open('photo_for_prod.jpg', 'wb') as file:
                    file.write(image_buffer.read())
                bot.send_photo(chat_id, photo=open('photo_for_prod.jpg', 'rb'), caption=message_text,
                               reply_markup=reply_markup)
    bot.send_message(chat_id, "Вернуться назад к категориям:", reply_markup=InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Назад", callback_data=f"back_to_cat")]]))


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


@bot.message_handler(commands=['cart'])
def checkout(message):
    user_id = message.from_user.id
    global current_state
    current_state[user_id] += 1
    if current_state[user_id] != num_states[user_id] + 1:
        pass
    elif user_id not in cart or not cart[user_id]:
        bot.send_message(chat_id=message.chat.id, text="Ваша корзина пуста.")
    else:
        global total_price, to_database_product, to_database_quantity
        total_price = 0
        products_text = []
        to_database_product = []
        to_database_quantity = []
        for product_id in cart[user_id]:
            product = next((p for p in products if p["id_spares"] == product_id), None)
            if product:
                quantity = cart[user_id].get(product_id, 0)
                product_text = f"{product['name_spares']} - ₽{product['price_spares']} - {quantity} шт."
                products_text.append(product_text)
                total_price += int(product["price_spares"]) * quantity
                to_database_product.append(product_id)
                to_database_quantity.append(quantity)
        message_text = "Ваша корзина:\n\n"
        message_text += "\n".join(products_text)
        message_text += f"\n\nИтого: ₽{total_price}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="Оформить заказ", callback_data="user_data")],
                                             [InlineKeyboardButton(text="Назад", callback_data=f"back_to_models")], [
                                                 InlineKeyboardButton(text="Очистить корзину",
                                                                      callback_data=f"clear_cart")]])
        bot.send_message(chat_id=message.chat.id, text=message_text, reply_markup=reply_markup)


def username(message):
    msg = bot.reply_to(message, "Пожалуйста, предоставьте выше ФИО. Данные вводите именно в таком порядке и через "
                                "пробел:")
    bot.register_next_step_handler(msg, process_name_step)


def process_name_step(message):
    global msg_user
    name = message.text
    msg_user = message
    msg = bot.reply_to(message, "Теперь, введите ваш номер телефона в формате +79XXXXXXXXX:")
    bot.register_next_step_handler(msg, process_phone_step, name)


def process_phone_step(message, name):
    phone = message.text
    msg = bot.reply_to(message, "Введите адрес доставки:")
    bot.register_next_step_handler(msg, process_address_step, name, phone)


def process_address_step(message, name, phone):
    global choose_day_msg, client_name, client_phone, address
    address = message.text
    client_name = name
    client_phone = phone
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="Понедельник", callback_data="Понедельник")],
                                         [InlineKeyboardButton(text="Вторник", callback_data="Вторник")],
                                         [InlineKeyboardButton(text="Среда", callback_data="Среда")],
                                         [InlineKeyboardButton(text="Четверг", callback_data="Четверг")],
                                         [InlineKeyboardButton(text="Пятница", callback_data="Пятница")],
                                         [InlineKeyboardButton(text="Суббота", callback_data="Суббота")],
                                         [InlineKeyboardButton(text="Воскресенье", callback_data="Воскресенье")]])
    choose_day_msg = bot.reply_to(message, "Выберите день недели:", reply_markup=reply_markup)


def process_delivery_day_step(message):
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="10:00 - 14:00", callback_data="time_10:00 - 14:00")],
         [InlineKeyboardButton(text="14:30 - 17:30", callback_data="time_14:30 - 17:30")],
         [InlineKeyboardButton(text="18:00 - 22:00", callback_data="time_18:00 - 22:00")]])
    bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=message.message_id, reply_markup=reply_markup)


def process_delivery_time_step(message, name, phone, address, delivery_day, delivery_time):
    chat_id = message.chat.id
    nasupat = name.split()

    cursor.execute(f'SELECT * FROM dbo.shopping_cart')
    rows = cursor.fetchall()
    id_cart = int(len(rows) + 1)

    cursor.execute(f'SELECT * FROM dbo.client')
    rows = cursor.fetchall()
    id_client = int(len(rows) + 1)

    cursor.execute(f'SELECT * FROM dbo.delivery')
    rows = cursor.fetchall()
    id_delivery = int(len(rows) + 1)

    cursor.execute("insert into shopping_cart(id_shopping_cart, id_spares, quantity, sum) values (?, ?, ?, ?)",
                   (id_cart, ";".join([str(r) for r in to_database_product]),
                    ";".join([str(r) for r in to_database_quantity]), total_price))

    bd.commit()
    cursor.execute("INSERT INTO dbo.client (id_client, tele_id, name_client, surname_client, patronymic_client, "
                   "number_client, address_client) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (id_client, str(msg_user.from_user.username), nasupat[1], nasupat[0], nasupat[2], str(phone),
                    address))

    bd.commit()
    cursor.execute("INSERT INTO dbo.delivery (id_delivery, id_client, id_shopping_cart, delivery_time) VALUES (?, ?, ?, ?)",
                   (id_delivery, id_client, id_cart, delivery_day + " " + delivery_time))

    bd.commit()
    users[msg_user.from_user.username] = [chat_id, id_delivery]
    bot.send_message(message.chat.id, f"Спасибо, {name}! Скоро с вами свяжется администратор для подтверждения заказа.")

    handle_database_changes(id_delivery, delivery_time)


def handle_database_changes(id_delivery, delivery_time):
    query = "SELECT id_delivery, confirmation FROM delivery WHERE confirmation IN ('Одобрено', 'Отклонено') AND id_delivery = ?"
    last_state = set()

    while True:
        cursor.execute(query, id_delivery)
        current_state = set(tuple(row) for row in cursor.fetchall())

        new_items = current_state - last_state
        for item in new_items:
            id_delivery, confirmation = item
            if confirmation == 'Одобрено':
                for user_id, chat_id in users.items():
                    if id_delivery in chat_id:

                        query_delivery = "SELECT delivery_time FROM delivery WHERE id_delivery = ?"
                        cursor.execute(query_delivery, id_delivery)
                        result_delivery = cursor.fetchone()
                        delivery_time = result_delivery[0].split()

                        query_shopping_cart = "SELECT sum FROM shopping_cart WHERE id_shopping_cart = ?"
                        cursor.execute(query_shopping_cart, id_delivery)
                        result_shopping_cart = cursor.fetchone()
                        total_sum = result_shopping_cart[0] if result_shopping_cart else None

                        bot.send_message(chat_id[0],
                                         f"Заказ подтвержден! Ваш заказ будет доставлен курьером в день недели: {delivery_time[0]} с "
                                         f"{delivery_time[1]}. Оплата при получении заказа. Сумма: {total_sum}")

            if confirmation == 'Отклонено':
                for user_id, chat_id in users.items():
                    if id_delivery in chat_id:
                        bot.send_message(chat_id[0],
                                         "К сожалению, ваш заказ был отклонён администратором, попробуйте ещё раз позднее!")

        last_state = current_state
        time.sleep(10)


bot.polling(none_stop=True)

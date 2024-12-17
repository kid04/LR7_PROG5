import time
import requests
from flask import Flask, render_template
from flask_sock import Sock
from xml.etree import ElementTree as ET
from observers import Observable, Observer
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
sock = Sock(app)
socks = []

class CurrencyObserver(Observer):
    def __init__(self, sock, currency):
        self.sock = sock
        self.currency = currency
        init_cur = cclass.get_currency(self.currency)
        if init_cur:
            self.update({self.currency: init_cur})

    def update(self, result) -> None:
        if self.sock.connected:
            if self.currency in result:
                data = f"{result[self.currency][0]}: {result[self.currency][1][0]},{result[self.currency][1][1]}"
                self.sock.send(data)
            else:
                self.sock.send(f'no such currency as "{self.currency}"')
                cclass.observers.remove(self)
        else:
            cclass.observers.remove(self)

class CurrenciesLst(Observable):
    def __init__(self, id_lst, limit=1000):
        super().__init__()
        self.__id_list = id_lst
        self.__cur_dict = {}
        self.last_time = 0
        self.limit = limit

    def get_currencies(self) -> dict:
        if time.time() - self.last_time < self.limit:
            time.sleep((self.limit - time.time() + self.last_time)/1000)
        self.last_time = time.time()
        cur_res_str = requests.get('http://www.cbr.ru/scripts/XML_daily.asp')
        result = {}

        root = ET.fromstring(cur_res_str.content)
        valutes = root.findall(
            "Valute"
        )
        update = False
        for _v in valutes:
            valute_charcode = _v.find('CharCode').text

            value = tuple(int(x) for x in _v.find('Value').text.split(','))
            if self.__cur_dict.get(valute_charcode, ["No", "ne"])[1] != value:
                update = True
                valute_cur_name = _v.find('Name').text
                print(valute_charcode)
                if _v.find('Nominal').text != '1':
                    valute_cur_nominal = int(_v.find('Nominal').text)
                    result[valute_charcode] = (valute_cur_name, value, valute_cur_nominal)
                else:
                    result[valute_charcode] = (valute_cur_name, value)
        if update:
            self.__cur_dict = result
        self.notify_observers()

    def notify_observers(self) -> None:
        for observer in self.observers:
            observer.update(self.__cur_dict)

    def get_currency(self, cur):
        if self.__cur_dict.get(cur, False):
            return self.__cur_dict[cur]


@app.route('/')
def index():
    return render_template('index.html')

@sock.route('/echo')
def echo(sock):
    while True:
        data = sock.receive()
        observer = CurrencyObserver(sock, data)
        cclass.register(observer)

cclass = CurrenciesLst(['R01090B', 'R01335', 'R01700J'])
cclass.get_currencies()

scheduler = BackgroundScheduler()
job = scheduler.add_job(cclass.get_currencies, 'interval', minutes=0.2)
scheduler.start()

app.run()


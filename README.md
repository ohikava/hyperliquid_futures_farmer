схема работы

1. выбирает рандомно монеты
2. для каждой монеты запускает рандомную покупку по мейкеру для перпа 1
3. после того, как приходит уведомление об открытии соответсвующей позиции, открывает по маркету противоположную на перп 2.
    для каждой позиции, генерируется уникальная пауза в определенном промежутке
4. В бесконечном цикле для каждой пары кошельков, для каждой позиции проверяется время, не пора ли закрывать. Если пора, то запускается функцияя для закрытия позиции по мейкеру
    функция создает два противоположных ордера по мейкеру для двух кошельков
    когда один из ордеров исполняется, второй удаляется и позиция закрывается по маркету 
5. После закрытия позции, происходит пересчёт открытых позиции и если, что открывается новая 


итого. открытие по мейкеру + открытие по тейкеру + закрытие по мейкеру + закрытие по тейкеру
0.010 + 0.010 + 0.035 + 0.035 = 0.09
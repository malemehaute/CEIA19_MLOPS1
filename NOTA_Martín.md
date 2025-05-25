**TO DO PROBAR DIFERENTES MODELOS CON VALORES DEFAULT**

* Ridge
* LASSO
* SVR
* LightGBM (probablemente el que mejor ande, probar usando su propio encoding en vez del Tgt Enc)
* 
* Nota martín: lo que yo creo que habría que hacer:

* Probar diferentes modelos con valores default sobre todas las variables
* Alguno de esos va a andar notablemente mejor que los demás (seguramente LightGBM)
* Agarrar el que sea preferible y hacer backward selection probando de dropear `Number_of_Ads`, `no_guest` y `sentiment_encoded` a ver si la performance mejora (recordar que estamos midiendo RMSE)
* Ahí hacer HP tuning con optuna y w&b

Recordar que LightGBM usa su propio target encoder, ver [ref](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMRegressor.html#lightgbm.LGBMRegressor) e [integrar con optuna](https://optuna-integration.readthedocs.io/en/stable/reference/index.html#lightgbm).

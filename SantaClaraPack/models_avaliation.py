import optuna
from joblib import dump, load
from sklearn.metrics import mean_absolute_error, median_absolute_error, r2_score
from SantaClaraPack.Models.PreProcessors import *
from SantaClaraPack.Banco.Dados import Dados
from SantaClaraPack.Optimizer.Optimizer import Optimizer
from SantaClaraPack.Plot.Plot import Plot

if __name__ == '__main__':
    desired_width = 320
    pd.set_option('display.width', desired_width)
    pd.set_option('display.max_columns', 100)


    dao = Dados()
    df_vazao = dao.get_vazao(posto=1, classe='Vazao', data_inicial='2000-01-01', data_final='2016-12-31')
    df_vazao = pd.DataFrame(df_vazao.iloc[:, 1:4])
    df_vazao.drop(columns=['num_posto'], inplace=True)
    df_vazao.set_index(keys=['dat_medicao'], inplace=True)

    df_chuva = dao.get_gridded_data(
        classe='Chuva',
        data_inicial='2000-01-01',
        data_final='2016-12-31',
        lat_inicial=-22.4,
        lat_final=-21.2,
        lon_inicial=-44.6,
        lon_final=-44.2,
    )

    pre = PreProcessors()
    gridded = GriddedDataProcessor()

    df_chuva_transform = gridded.transform(
        df=df_chuva,
        index='dat_medicao',
        cols=['val_lat', 'val_lon'],
        value='val_precip',
        var_name='chuva',
        agg='sum',
    )

    # Formando X e y
    X = pd.concat(objs=[df_vazao[['val_vaz_natr']], df_chuva_transform], sort=True, axis=1)
    y = df_vazao[['val_vaz_natr']]

    # Normalização dos dados

    # Separação nos arquivos de treino e teste
    '''Separação sequencial por ser um time series'''
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, stratify=None, shuffle=False)

    # Avaliacao do modelo modelo com hyper-tunning
    optimize = Optimizer()

    study = optuna.create_study(
        storage='sqlite:///Optimizer/optimize_tests.db',
        direction='maximize',
        study_name='optimize',
        load_if_exists=True
    )

    optimize.get_data(X=X_train, y=y_train, X_test=X_test, y_test=y_test)
    study.optimize(optimize, n_trials=50)

    # Cria e salva melhor configuração
    model = optimize.create_best_model(params=study.best_params)
    print('Criação do modelo com os melhores parametros pesquisados:')
    [print(k, v) for k, v in model.best_params_.items()]

    dump(value=model, filename=r'Models/mlp_posto_1.joblib')

    window = WindowProcessor()
    X_test_lag, y_test_lag = window.transform(
        X=X_test,
        y=y_test,
        n_in=study.best_params['window_neg'],
        n_out=0
    )

    y_hat = model.predict(X=X_test_lag)

    # Scores
    print('MAE test: {:}'.format(mean_absolute_error(y_true=y_test_lag, y_pred=y_hat)))
    print('MedAE test: {:}'.format(median_absolute_error(y_true=y_test_lag, y_pred=y_hat)))
    print('R2 test: {:}'.format(r2_score(y_true=y_test_lag, y_pred=y_hat)))

    # plot
    plot = Plot()
    plot.plot_prediction_compararison(y_true=y_test_lag['val_vaz_natr'].values, y_pred=y_hat, times=y_test_lag.index)
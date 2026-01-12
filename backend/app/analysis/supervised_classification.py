def supervised_classification(X,y,method='logistic_regression',params=None):
    
    """ 
    Perform supervised classification on a dataset with a binary target.
    """ 

    import pandas as pd
    import matplotlib.pyplot as plt
    from sklearn.model_selection import train_test_split
    from sklearn import metrics
    from sklearn.metrics import accuracy_score, confusion_matrix, roc_curve, auc, classification_report, recall_score

    if params is None:
        params = {}  # default to empty dictionary

    X_train,  X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    if method == 'logistic_regression':
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(**params, solver="liblinear")
    elif method == 'svm':
        from sklearn import svm
        model = svm.SVC(**params, probability=True)
    elif method == 'naive_bayes':
        from sklearn.naive_bayes import GaussianNB
        model = GaussianNB()
    elif method == 'decision_trees':
        from sklearn.tree import DecisionTreeClassifier
        model = DecisionTreeClassifier(**params)
    elif method == 'random_forest':
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(**params)
    elif method == 'bagging':
        from sklearn.ensemble import BaggingClassifier
        model = BaggingClassifier(**params)
    elif method == 'boosting':  
        from sklearn.ensemble import GradientBoostingClassifier
        model = GradientBoostingClassifier(**params)
    elif method == 'stacking':
        from sklearn.ensemble import StackingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

        estimators = [
            ('lr', LogisticRegression(max_iter=1000)),
            ('rf', RandomForestClassifier()),
        ]

        model = StackingClassifier(
            estimators=estimators,
            final_estimator=GradientBoostingClassifier(),
        )
    else:
        raise ValueError("Unsupported method.") 

    model.fit(X_train, y_train)

    # Predictions on test set
    y_pred = model.predict(X_test)
    cm = metrics.confusion_matrix(y_test, y_pred)
    cm_df = pd.DataFrame(cm, 
                        columns=['predicted 0', 'predicted 1 '],
                        index=['is 0', 'is 1'])
    print(cm_df)    
    print(classification_report(y_test, y_pred))
    y_pred_prob = model.predict_proba(X_test)
    y_pred_prob_df = pd.DataFrame(y_pred_prob, columns=['class_0_pp', 'class_1_pp'])
    # Find fpr, tpr
    fpr, tpr, _ = metrics.roc_curve(y_test, y_pred_prob_df['class_1_pp'])
    # Find auc
    roc_auc = metrics.auc(fpr, tpr)
    recall = recall_score(y_test, y_pred, pos_label=1)
    n_samples = len(y_test)

    '''
    # Plot of a ROC curve for class 1 
    plt.figure(figsize=[8,8])
    # Plot fpr, tpr
    plt.plot(fpr, tpr, color='darkorange', lw = 2, label = 'ROC curve (area = %0.2f)' % roc_auc)
    plt.plot([0, 1], [0, 1], 'k--', linewidth=4)
    plt.xlim([-0.05, 1.0])
    plt.ylim([-0.05, 1.05])
    plt.xlabel('False Positive Rate', fontsize=18)
    plt.ylabel('True Positive Rate', fontsize=18)
    plt.title('Receiver operating characteristic for cancer detection', fontsize=18)
    plt.legend(loc="lower right")
    plt.show()
    '''
    
    return model,roc_auc, recall, n_samples

def param_optimization(model,parameters,X_train, y_train, X_test, y_test):
    """
    Perform hyperparameter optimization using GridSearchCV.
    """
    from sklearn.model_selection import GridSearchCV
    from sklearn.metrics import accuracy_score,classification_report

    grid = GridSearchCV(model, parameters, cv=5, scoring='accuracy')
    grid.fit(X_train, y_train)
    print("Best parameters: ", grid.best_params_)
    print("Best cross-validation accuracy: ", grid.best_score_)     

    best_model = grid.best_estimator_
    # Predictions on test set
    y_pred = best_model.predict(X_test)

    print("Test Accuracy:", accuracy_score(y_test, y_pred))
    print(classification_report(y_test, y_pred))

    return grid.best_params_

def roc_plot(X,y,models,params):

    import matplotlib.pyplot as plt

    plt.figure(figsize=[8,8])
    plt.xlim([-0.05, 1.0])
    plt.ylim([-0.05, 1.05])

    for model in models:
        mod,fpr,tpr,roc = supervised_classification(X,y,method=model,params=params[model])
        plt.plot(fpr, tpr, lw = 2, label = '%s ROC curve (area = %0.2f)' % (model,roc))

    plt.xlabel('False Positive Rate', fontsize=18)
    plt.ylabel('True Positive Rate', fontsize=18)
    plt.title('Receiver Operating Characteristic: M', fontsize=18)
    plt.legend(loc="lower right")
    plt.show()

def predictions(X,y,model):
    
    """ 
    Perform predications on a dataset with a binary target.
    """ 

    import pandas as pd
    import matplotlib.pyplot as plt
    from sklearn import metrics
    from sklearn.metrics import accuracy_score, confusion_matrix, roc_curve, auc, classification_report

    y_pred = model.predict(X)
    cm = metrics.confusion_matrix(y, y_pred)
    cm_df = pd.DataFrame(cm, 
                        columns=['predicted 0', 'predicted 1 '],
                        index=['is 0', 'is 1'])
    print(cm_df)    
    print(classification_report(y, y_pred))
    y_pred_prob = model.predict_proba(X)
    y_pred_prob_df = pd.DataFrame(y_pred_prob, columns=['class_0_pp', 'class_1_pp'])
    # Find fpr, tpr
    fpr, tpr, _ = metrics.roc_curve(y, y_pred_prob_df['class_1_pp'])
    # Find auc
    roc_auc = metrics.auc(fpr, tpr)
   
    # Plot of a ROC curve for class 1 
    plt.figure(figsize=[8,8])
    # Plot fpr, tpr
    plt.plot(fpr, tpr, color='darkorange', lw = 2, label = 'ROC curve (area = %0.2f)' % roc_auc)
    plt.plot([0, 1], [0, 1], 'k--', linewidth=4)
    plt.xlim([-0.05, 1.0])
    plt.ylim([-0.05, 1.05])
    plt.xlabel('False Positive Rate', fontsize=18)
    plt.ylabel('True Positive Rate', fontsize=18)
    plt.title('Receiver operating characteristic', fontsize=18)
    plt.legend(loc="lower right")
    plt.show()
    
    return model,fpr,tpr,roc_auc
    
import numpy as np

def bootstrap_or_ci(model_cls, X, y, feature_names, params=None, n_boot=1000):
    ors = {f: [] for f in feature_names}

    for _ in range(n_boot):
        idx = np.random.choice(len(X), len(X), replace=True)
        X_b = X.iloc[idx]
        y_b = y.iloc[idx]

        model = model_cls(**(params or {}))
        model.fit(X_b, y_b)

        for f, coef in zip(feature_names, model.coef_[0]):
            ors[f].append(np.exp(coef))

    results = {}
    for f, values in ors.items():
        results[f] = {
            "OR": np.mean(values),
            "CI": np.percentile(values, [2.5, 97.5])
        }

    return results

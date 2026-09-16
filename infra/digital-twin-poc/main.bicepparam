using './main.bicep'

param environment = 'dev'
param baseName = 'tiger-edge'
param skuName = 'Standard'
// Use main.bicep tag defaults so the environment tag follows the environment parameter.

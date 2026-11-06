pipeline {
    agent any
    stages {
        stage('Clone') {
            steps { checkout scm }
        }
        stage('Build Docker Image') {
            steps { bat 'docker build -t event-registration-system:v1 .' }
        }
        stage('Run Container') {
            steps {
                bat 'docker rm -f event-app || exit 0'
                bat 'docker run -d -p 5000:5000 --name event-app event-registration-system:v1'
            }
        }
    }
}
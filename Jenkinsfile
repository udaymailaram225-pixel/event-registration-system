pipeline {
    agent any
    stages {
        stage('Clone') {
            steps { checkout scm }
        }
        stage('Build Docker Image') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'docker build -t event-registration-system:v1 .'
                    } else {
                        bat 'docker build -t event-registration-system:v1 .'
                    }
                }
            }
        }
        stage('Run Container') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'docker rm -f event-app || true'
                        sh 'docker run -d -p 5000:5000 --name event-app event-registration-system:v1'
                    } else {
                        bat 'docker rm -f event-app || exit 0'
                        bat 'docker run -d -p 5000:5000 --name event-app event-registration-system:v1'
                    }
                }
            }
        }
    }
}

from locust import HttpUser, task, between

class ConsumerUser(HttpUser):
    wait_time = between(1, 2)  # Wait time between tasks

    @task
    def load_test(self):
        self.client.get("/")


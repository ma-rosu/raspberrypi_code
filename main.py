# import os
# import time
# from threading import Thread
# import cv2
#
# from agents.fire_agent import FireAgent
# from agents.speak_agent import SpeakAgent
# from agents.fall_agent import FallAgent
# from agents.human_interaction_agent import HumanInteractionAgent
# from push_notification import push_notification
#
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#
# cap = cv2.VideoCapture(0)
# fall_agent = FallAgent()
# human_interaction_agent = HumanInteractionAgent()
# fire_agent = FireAgent()
#
#
# last_fall_time = 0
# last_sleep_time = 0
# last_move_time = 0
# last_fire_time = 0
# last_smoke_time = 0
# time_cooldown = 300
# fire_cooldown = 30
#
# def speak_fall():
#     SpeakAgent('fall')
#
# def speak_move():
#     SpeakAgent('move')
#
# def speak_sleep():
#     SpeakAgent('sleep')
#
# while True:
#     ret, frame = cap.read()
#     if not ret:
#         break
#
#     resized_frame = cv2.resize(frame, (224, 224))
#     norm_frame = resized_frame / 255.0
#
#     if fire_agent.check(norm_frame):
#         current_time = time.time()
#         if current_time - last_fire_time > fire_cooldown:
#             last_fire_time = current_time
#             push_notification('FIRE DETECTED', 'There was fire detected. Check the livestream on the app!')
#
#
#     if fall_agent.check(frame):
#         current_time = time.time()
#         if current_time - last_fall_time > time_cooldown:
#             last_fall_time = current_time
#             push_notification('FALL DETECTED', 'The person in your care has fallen. Try contacting them.')
#             Thread(target=speak_fall).start()
#
#     human_interaction_agent.init_bbox(frame)
#
#     if human_interaction_agent.should_sleep():
#         current_time = time.time()
#         if current_time - last_sleep_time > time_cooldown:
#             last_sleep_time = current_time
#             Thread(target=speak_sleep).start()
#
#     if human_interaction_agent.should_move():
#         current_time = time.time()
#         if current_time - last_move_time > time_cooldown:
#             last_move_time = current_time
#             Thread(target=speak_move).start()
#
#
#
#     cv2.imshow("Detecție", frame)
#
#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break
#
# cap.release()
# cv2.destroyAllWindows()

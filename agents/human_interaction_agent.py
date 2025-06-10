# import os
# import datetime
# import numpy as np
# from ultralytics import YOLO
# import time
#
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#
# class HumanInteractionAgent:
#     def __init__(self):
#         self.model = YOLO(os.path.abspath(os.path.join(BASE_DIR,'..','models','human_detection_yolo', 'yolov8s.pt')))
#         self.boxes = None
#         self.time_1 = time.time()
#         self.time_2 = time.time()
#         self.prev_centers = []
#         self.frames_without_human = 0
#
#     def _get_center(self, box):
#         x1, y1, x2, y2 = box.xyxy[0].tolist()
#         center_x = (x1 + x2) / 2
#         center_y = (y1 + y2) / 2
#         return (int(center_x), int(center_y))
#
#     def _check_for_boxes(self, frame):
#         human_results = self.model.predict(source=frame, imgsz=640, conf=0.7, verbose=False)
#         boxes = human_results[0].boxes
#
#         if boxes is not None and boxes.cls is not None:
#             cls = boxes.cls.cpu().numpy()
#             mask = cls == 0
#             filtered_boxes = boxes[mask]
#             return filtered_boxes
#
#         return None
#
#     def _check_for_sleeping_hours(self):
#         current_hour = datetime.datetime.now().hour
#         return current_hour >= 20 or current_hour < 8
#
#     def init_bbox(self, frame):
#         self.boxes = self._check_for_boxes(frame)
#
#     def should_move(self):
#         if self.boxes is None or len(self.boxes) == 0:
#             self.frames_without_human += 1
#         else:
#             self.frames_without_human = 0
#
#         moved = False
#         new_centers = []
#
#         if self.boxes is not None and len(self.boxes) > 0:
#             for box in self.boxes:
#                 center = self._get_center(box)
#                 new_centers.append(center)
#
#             if self.prev_centers:
#                 distances = []
#                 for c1, c2 in zip(self.prev_centers, new_centers):
#                     dist = np.linalg.norm(np.array(c1) - np.array(c2))
#                     distances.append(dist)
#
#                 avg_dist = np.mean(distances)
#                 print(avg_dist)
#                 if avg_dist > 50:  # movement threshold
#                     moved = True
#                     self.time_1 = time.time()
#
#             self.prev_centers = new_centers
#
#         self.time_2 = time.time()
#         if (not moved and (self.time_2 - self.time_1 > 3600) and # time threshold (seconds)
#                 not self._check_for_sleeping_hours() and self.frames_without_human < 30): # frames threshold
#             return True
#
#         return False
#
#     def humans_number(self):
#         return len(self.boxes)
#
#     def should_sleep(self):
#         if datetime.datetime.now().hour == 21 and datetime.datetime.now().minute == 00 and datetime.datetime.now().second == 00:
#             return True

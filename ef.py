# DroidCam OpenCV test
import cv2

url = "http://192.168.8.253:4747/video"  # your MJPEG URL
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Cannot open stream. Check URL and network.")
    exit(1)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame read failed.")
        break
    cv2.imshow("DroidCam (MJPEG)", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
        break

cap.release()
cv2.destroyAllWindows()

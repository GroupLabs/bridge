import cv2
import numpy as np

# Load the classes
with open("coco.names", "r") as f:
    classes = [line.strip() for line in f.readlines()]


# Load YOLO
net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")
layer_names = net.getLayerNames()

unconnected_out_layers = net.getUnconnectedOutLayers()
if unconnected_out_layers.ndim == 1:
    # There's only one unconnected output layer
    output_layers = [layer_names[unconnected_out_layers[0] - 1]]
else:
    # There are multiple unconnected output layers
    output_layers = [layer_names[i[0] - 1] for i in unconnected_out_layers]

# Open webcam
cap = cv2.VideoCapture(0)

while True:
    # Capture frame-by-frame
    ret, img = cap.read()
    img = cv2.resize(img, None, fx=0.4, fy=0.4)
    height, width, channels = img.shape

    # Detecting objects
    blob = cv2.dnn.blobFromImage(img, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)

    # Showing informations on the screen
    class_ids = []
    confidences = []
    boxes = []
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5:
                # Object detected
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)

                # Rectangle coordinates
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)

                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

    font = cv2.FONT_HERSHEY_PLAIN
    for i in range(len(boxes)):
        if i in indexes:
            x, y, w, h = boxes[i]
            class_id = class_ids[i]
            label = classes[class_id]
            confidence = confidences[i]
            text = f'{label} {confidence:.2f}'
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, text, (x, y - 5), font, 1, (0, 255, 255), 1)


    cv2.imshow("Image", img)

    # Break the loop on 'q' key press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
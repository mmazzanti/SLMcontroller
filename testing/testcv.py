import cv2
import numpy as np
import os

file = "deformation_correction_pattern/CAL_LSH0802160_750nm.bmp"
#file = os.path.join(os.getcwd(), 'deformation_correction_pattern', 'CAL_LSH0802160_750nm.bmp');
img = cv2.imread(file, -1)
print(img)
cv2.imshow("image", img)
data = np.array(img)
print(data)
print("Max : ",np.amax(data))
cv2.waitKey(0)
cv2.destroyAllWindows()
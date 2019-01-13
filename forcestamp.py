import numpy as np
from scipy.ndimage.filters import maximum_filter, minimum_filter
import itertools
import bch
import ellipses


def findLocalPeaks(img, threshold=0.5, kernal=3):
    # apply the local maximum filter; all pixel of maximum value
    # in their neighborhood are set to 1
    local_max_g = maximum_filter(img, kernal)
    local_min_g = minimum_filter(img, kernal)

    # store local maxima
    local_max = (local_max_g == img)

    # difference between local maxima and minima
    diff = ((local_max_g - local_min_g) > threshold)
    # insert 0 where maxima do not exceed threshold
    local_max[diff == 0] = 0

    return local_max


def findCircles(dots, radius):
    # find circle center candidates from two dots on the circle

    # extract coordinates from dots
    x1 = dots[0][0]
    x2 = dots[1][0]
    y1 = dots[0][1]
    y2 = dots[1][1]

    # distance between pt1 and pt2
    q = np.sqrt(((x2 - x1) * (x2 - x1)) + ((y2 - y1) * (y2 - y1)))

    # prepare an array to return center candidates
    circleCenters = []

    # middle point
    x3 = (x1 + x2) / 2
    y3 = (y1 + y2) / 2

    x = x3 + np.sqrt(radius ** 2 - (q / 2) ** 2) * (y1 - y2) / q
    y = y3 + np.sqrt(radius ** 2 - (q / 2) ** 2) * (x2 - x1) / q
    circleCenters.append((x, y))

    x = x3 - np.sqrt(radius ** 2 - (q / 2) ** 2) * (y1 - y2) / q
    y = y3 - np.sqrt(radius ** 2 - (q / 2) ** 2) * (x2 - x1) / q
    circleCenters.append((x, y))

    return circleCenters


def distance(pt1, pt2):
    # calculate distance between two points
    return np.sqrt((pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2)


def findPeakCoord(img):
    # return peak coordinates from input peak image
    peaks = [tuple(coords) for coords in zip(*np.where(img == True))]
    # print(peaks)
    return peaks


def findMarker(img, markerRadius, distanceTolerance=1):
    # find marker pin peaks from the peak image
    # distanceTolerance: tolerance when finding marker center candidates
    peaks = findPeakCoord(img)

    circleCenters = []
    # make combination of two to find circle peaks
    for peaks_comb in itertools.combinations(peaks, 2):
        if distance(peaks_comb[0], peaks_comb[1]) < markerRadius * 2.1:
            circleCenters_2 = findCircles(peaks_comb, markerRadius)
            # parse the obtained center candidates
            for circleCenters_1 in circleCenters_2:
                circleCenters.append(circleCenters_1)

    # find marker center candidates by given radidus
    markerCenters = []
    for cnt in circleCenters:
        distanceCount = 0
        for peak in peaks:
            if distance(cnt, peak) < markerRadius + distanceTolerance and \
               distance(cnt, peak) > markerRadius - distanceTolerance:
                distanceCount += 1
        # if there are less than 5 dots on the circle
        if distanceCount > 4:
            markerCenters.append(cnt)

    # cluster and average marker center candidates to find accurate centers
    markerCentersClustered = []
    numCluster = 0
    for cnt in markerCenters:
        # for first marker, just add a new cluster
        if numCluster == 0:
            markerCentersClustered.append([cnt])
            numCluster += 1
        else:
            currentCluster = 0
            isNew = True
            minDist = 1000
            for i in range(len(markerCentersClustered)):
                # check distance from existing cluster centers
                dist = distance(cnt, markerCentersClustered[i][0])
                minDist = np.minimum(minDist, dist)
                if dist < markerRadius / 2:
                    # add the center point to current cluster
                    isNew = False
                    currentCluster = i
                    break
            if isNew:
                # if the point does not belong to any existing clusters
                if minDist > markerRadius * 2.1:  # do not overlap with others
                    numCluster += 1
                    markerCentersClustered.append([])
                    markerCentersClustered[numCluster - 1].append(cnt)
            else:
                markerCentersClustered[currentCluster].append(cnt)

    # average marker center candidates to get accurate centers
    markerCentersFiltered = []
    for cluster in markerCentersClustered:
        averageCoordX = 0
        averageCoordY = 0
        for coord in cluster:
            averageCoordX += coord[0]
            averageCoordY += coord[1]
        averageCoordX /= len(cluster)
        averageCoordY /= len(cluster)
        markerCentersFiltered.append((averageCoordX, averageCoordY))

    return markerCentersFiltered


def constraint(input, const_floor, const_ceil):
    # make input to be
    # const_floor < input < const_ceil
    if input < const_floor:
        input = const_floor
    elif input > const_ceil:
        input = const_ceil
    else:
        input = input
    return input


def detectDots(img, coords, area=4):
    # detect if there are peaks in dot candidates with kernals
    # for i in range(area):
        # for j in range(area):
    x_start = coords[0] - int(area / 2)
    y_start = coords[1] - int(area / 2)
    x_end = coords[0] + int(area / 2) + 1
    y_end = coords[1] + int(area / 2) + 1
    x_start = constraint(x_start, 0, np.shape(img)[0])
    y_end = constraint(y_end, 0, np.shape(img)[1])
    x_start = constraint(x_start, 0, np.shape(img)[0])
    y_end = constraint(y_end, 0, np.shape(img)[1])
    kernal = img[x_start:x_end, y_start:y_end]
    # print(kernal)
    # print(np.sum(kernal))
    if np.sum(kernal) >= 1:
        return 1
    else:
        return 0


def extractCode(img, markerRadius, distTolerance=3):
    n = 15
    # find marker pin peaks from the peak image
    peaks = findPeakCoord(img)

    # calculate temporary marker center
    centerPX = np.floor(np.shape(img)[0] / 2)
    centerPY = np.floor(np.shape(img)[1] / 2)
    markerCenter = (centerPX, centerPY)

    # find dots which are included in the marker
    trueDots = []
    for peak in peaks:
        dist = distance(markerCenter, peak)
        if dist < markerRadius + distTolerance and \
           dist > markerRadius - distTolerance:
            trueDots.append(peak)

    # print(trueDots)

    # find marker center from the true dots
    data = [[], []]
    for i in trueDots:
        data[0].append(i[0])
        data[1].append(i[1])
    lsqe = ellipses.LSqEllipse()
    lsqe.fit(data)
    center, width, height, phi = lsqe.parameters()
    # print('circle center: ', tuple(center))

    # make the dots as vectors from center point
    vecDots = []
    for dot in trueDots:
        vec = (dot[0] - center[0], dot[1] - center[1])
        vecMag = distance((0, 0), vec)
        vecPhs = np.arctan2(vec[1], vec[0])
        vecDots.append((vecMag, vecPhs))
    # print(np.rad2deg(vecPhs) % (360 / 15))

    # 15th power to remove phase shifts
    # print(vecDots[1])
    phaseError = 0
    for i in vecDots:
        phaseError += i[1] % (2 * np.pi / n)

    phaseError = phaseError / len(vecDots)
    # print('marker deg: ' + str(phaseError))

    # print(vecDots[0])
    vecDotsFixed = []
    for i in vecDots:
        vecDotsFixed.append((i[0], (i[1] - phaseError) % (2 * np.pi)))

    # print(vecDotsFixed)

    # fix vector representation to coordinates
    cartDotsFixed = []
    for vector in vecDotsFixed:
        x = center[0] + vector[0] * np.sin(vector[1])
        y = center[1] + vector[0] * np.cos(vector[1])
        cartDotsFixed.append((x, y))

    initDot = (center[0] + markerRadius, center[1])
    # print(initDot)

    codes = []
    dotRegions = []
    # specify dot regions
    initX = initDot[0] - center[0]
    initY = initDot[1] - center[1]
    initRad = np.arctan2(initX, initY)
    for j in range(n):
        destX = center[0] + \
            markerRadius * np.sin(initRad + j * 2 * np.pi / n)
        destY = center[1] + \
            markerRadius * np.cos(initRad + j * 2 * np.pi / n)
        dotRegions.append((destX, destY))

    codes = []
    for dot in dotRegions:
        isDot = 0
        for dotData in cartDotsFixed:
            if distance(dot, dotData) < 4:
                isDot = 1
        codes.append(isDot)

    # detect dots and extract codes from marker grid
    # for dots in dotRegions:
    #     result = detectDots(img, dots)
    #     codes.append(result)

    # codes = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    return codes, dotRegions


def recognizeID(msg, full=False):
    # recognize ID by the received codeword
    codeList = [
        [0],
        [32, 1, 34, 3, 68, 7, 8, 64, 14, 16, 81, 116, 104, 58, 29],
        [96, 65, 2, 115, 4, 102, 39, 9, 76, 78, 48, 19, 24, 57, 28],
        [97, 66, 5, 38, 41, 10, 77, 110, 112, 83, 20, 55, 56, 27, 92],
        [33, 67, 37, 6, 40, 105, 42, 13, 80, 82, 52, 21, 84, 26, 74],
        [98, 69, 119, 95, 11, 46, 111, 113, 23, 120, 59, 124, 93, 126, 63],
        [99, 70, 103, 108, 12, 79, 49, 51, 118, 88, 25, 123, 125, 62, 31],
        [35, 100, 71, 72, 107, 44, 15, 17, 50, 117, 86, 89, 122, 61, 30],
        [73, 18, 36],
        [75, 101, 106, 43, 45, 47, 114, 53, 22, 87, 121, 90, 60, 94, 85],
        [91, 109, 54],
        [127]
    ]

    # Recognize ID by full codeword.
    uniqueCodes = [
        np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.int),
        np.array([1, 0, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=np.int),
        np.array([1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0], dtype=np.int),
        np.array([1, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0], dtype=np.int),
        np.array([1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0], dtype=np.int),
        np.array([1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 0, 0], dtype=np.int),
        np.array([1, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0], dtype=np.int),
        np.array([1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0], dtype=np.int),
        np.array([1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0], dtype=np.int),
        np.array([1, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 0], dtype=np.int),
        np.array([1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0], dtype=np.int),
        np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], dtype=np.int)
    ]

    n = 15

    IDout = 0
    if full:
        for ID in range(len(uniqueCodes)):
            for code in uniqueCodes[ID]:
                recCode = bch.bchEncode15_7(msg)
                for i in range(n):
                    recCode_shift = np.roll(recCode, i)
                    if recCode_shift.tolist() == code.tolist():
                        IDout = ID
                        break

    else:
        for ID in range(len(codeList)):
            for code in codeList[ID]:
                if msg == code:
                    IDout = ID
                    break

    return IDout


def cropImage(img, pos, radius, margin=4):
    # crop image region surrounded by circle

    # img size
    width = np.shape(img)[0]
    height = np.shape(img)[1]

    posX = int(pos[0])
    posY = int(pos[1])

    # crop size
    crop = (radius + margin) * 2 + 1
    crop_half = radius + margin

    imgCropped = np.zeros((crop, crop))

    xMinFixed = 0
    xMaxFixed = crop
    yMinFixed = 0
    yMaxFixed = crop

    xMin = posX - crop_half
    xMax = posX + crop_half
    yMin = posY - crop_half
    yMax = posY + crop_half

    if xMin < 0:
        xMinFixed = -xMin
    if xMax >= width:
        xMaxFixed = crop + (width - xMax) - 1
    if yMin < 0:
        yMinFixed = -yMin
    if yMax >= height:
        yMaxFixed = crop + (height - yMax) - 1

    pxMin = constraint(posX - crop_half, 0, width)
    pxMax = constraint(posX + crop_half, 0, width)
    pyMin = constraint(posY - crop_half, 0, height)
    pyMax = constraint(posY + crop_half, 0, height)
    imgCropped[xMinFixed:xMaxFixed, yMinFixed:yMaxFixed] = \
        img[pxMin:pxMax + 1, pyMin:pyMax + 1]

    return imgCropped


def calculateForceVector(img):
    # calcuate vector of the applied force
    width = np.shape(img)[0]
    height = np.shape(img)[1]
    centerP = np.floor(np.shape(img)[0] / 2)

    vecX = 0
    vecY = 0
    for i in range(width):
        for j in range(height):
            vecMag = distance((i, j), (centerP, centerP))
            vecRad = np.arctan2(i - centerP, j - centerP)
            vecX += img[i, j] * vecMag * np.sin(vecRad)
            vecY += img[i, j] * vecMag * np.cos(vecRad)
    return (vecX, vecY)[::-1]


class marker:
    # posX: x coordinate (0-184)
    # posY: y coordinate (0-104)
    # ID: marker ID (0-11)
    # sumForce: force applied to relevant marker (0-?)
    # vecForce: vector of the applied force (0-1 vector? (dx, dy))
    # rotation (for assymetric markers)
    def __init__(self, img, imgPeak, markerRadius, pos):
        self.posX = pos[1]
        self.posY = pos[0]

        self.markerImg = cropImage(img, pos, markerRadius)

        self.markerImgPeak = cropImage(imgPeak, pos, markerRadius)

        self.code, self.dotRegions = extractCode(
            self.markerImgPeak,
            markerRadius
        )
        self.ID = recognizeID(bch.bchDecode15_7(self.code))
        # self.rotation = 0 TODO

    def vectorForce(self):
        return calculateForceVector(self.markerImg)

    def sumForce(self):
        return np.sum(self.markerImg)

# *****************************************************
#                                                    *
# Copyright 2018 Amazon.com, Inc. or its affiliates. *
# All Rights Reserved.                               *
#                                                    *
# *****************************************************
""" A sample lambda for style transfer"""
from threading import Thread, Event
import os
import numpy as np
import awscam
import cv2
import greengrasssdk


class LocalDisplay(Thread):
    """ Class for facilitating the local display of inference results
        (as images). The class is designed to run on its own thread. In
        particular the class dumps the inference results into a FIFO
        located in the tmp directory (which lambda has access to). The
        results can be rendered using mplayer by typing:
        mplayer -demuxer lavf -lavfdopts format=mjpeg:probesize=32 /tmp/results.mjpeg
    """

    def __init__(self, resolution):
        """ resolution - Desired resolution of the project stream """
        # Initialize the base class, so that the object can run on its own
        # thread.
        super(LocalDisplay, self).__init__()
        # List of valid resolutions
        RESOLUTION = {"1080p": (1920, 1080), "720p": (1280, 720), "480p": (858, 480)}
        if resolution not in RESOLUTION:
            raise Exception("Invalid resolution")
        self.resolution = RESOLUTION[resolution]
        # Initialize the default image to be a white canvas. Clients
        # will update the image when ready.
        self.frame = cv2.imencode(".jpg", 255 * np.ones([640, 480, 3]))[1]
        self.stop_request = Event()

    def run(self):
        """ Overridden method that continually dumps images to the desired
            FIFO file.
        """
        # Path to the FIFO file. The lambda only has permissions to the tmp
        # directory. Pointing to a FIFO file in another directory
        # will cause the lambda to crash.
        result_path = "/tmp/results.mjpeg"
        # Create the FIFO file if it doesn't exist.
        if not os.path.exists(result_path):
            os.mkfifo(result_path)
        # This call will block until a consumer is available
        with open(result_path, "w") as fifo_file:
            while not self.stop_request.isSet():
                try:
                    # Write the data to the FIFO file. This call will block
                    # meaning the code will come to a halt here until a consumer
                    # is available.
                    fifo_file.write(self.frame.tobytes())
                except IOError:
                    continue

    def set_frame_data(self, frame):
        """ Method updates the image data. This currently encodes the
            numpy array to jpg but can be modified to support other encodings.
            frame - Numpy array containing the image data of the next frame
                    in the project stream.
        """
        ret, jpeg = cv2.imencode(".jpg", cv2.resize(frame, self.resolution))
        if not ret:
            raise Exception("Failed to set frame data")
        self.frame = jpeg

    def join(self):
        self.stop_request.set()


def greengrass_infinite_infer_run():
    """ Entry point of the lambda function"""
    try:
        # Create an IoT client for sending to messages to the cloud.
        client = greengrasssdk.client("iot-data")
        iot_topic = "$aws/things/{}/infer".format(os.environ["AWS_IOT_THING_NAME"])
        # Create a local display instance that will dump the image bytes to a FIFO
        # file that the image can be rendered locally.
        local_display = LocalDisplay("480p")
        local_display.start()
        # The sample projects come with optimized artifacts, hence only the artifact
        # path is required.
        model_path = "/opt/awscam/artifacts/mxnet_style_FP32_FUSE.xml"
        # Load the model onto the GPU.
        client.publish(topic=iot_topic, payload="Loading style transfer model")
        model = awscam.Model(model_path, {"GPU": 1})
        client.publish(topic=iot_topic, payload="Style transfer model loaded")
        # The style model is classified as a segmentation model, in the sense that the output is
        # an image.
        model_type = "segmentation"
        # The height and width of the training set images
        input_height = 224
        input_width = 224
        # Do inference until the lambda is killed.
        while True:
            # Get a frame from the video stream
            ret, frame = awscam.getLastFrame()
            if not ret:
                raise Exception("Failed to get frame from the stream")
            # Resize frame to the same size as the training set.
            frame_resize = cv2.resize(frame, (input_height, input_width))
            # Run the images through the inference engine and parse the results
            infer_output = model.doInference(frame_resize)
            parsed_results = infer_output["Convolution_last_conv"]
            parsed_results = np.reshape(
                parsed_results[::-1], (input_height, input_width, 3), order="F"
            )
            parsed_results = np.rot90(parsed_results)
            # Set the next frame in the local display stream.
            local_display.set_frame_data(parsed_results * 2)

    except Exception as ex:
        print("Error", ex)
        client.publish(
            topic=iot_topic, payload="Error in style transfer lambda: {}".format(ex)
        )


greengrass_infinite_infer_run()

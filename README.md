# deeplens-sample

## Instructions without ssh

```bash
mplayer –demuxer lavf /opt/awscam/out/ch1_out.h264

mplayer –demuxer lavf -lavfdopts format=mjpeg:probesize=32 /tmp/results.mjpeg
```

## Instructions with ssh

```bash
export DL_IP_ADDR="192.168.150.106"

ssh aws_cam@$DL_IP_ADDR cat /opt/awscam/out/ch1_out.h264 |
  mplayer –demuxer lavf -cache 8092 -

ssh aws_cam@$DL_IP_ADDR cat /tmp/\*results.mjpeg |
  mplayer –demuxer lavf -cache 8092 -lavfdopts format=mjpeg:probesize=32 -
```

### CloudWatch Insight

```sql
fields @message
| filter @message =~ 'Greengrass Message'
| sort @timestamp desc
```

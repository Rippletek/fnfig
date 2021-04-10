# fnfig

Interface Generator for Alibaba Cloud FNF Service

fnfig是一个辅助开发阿里云FNF应用的代码框架。只需定义一个FIG DSL文件来描述代码逻辑，fnfig会生成好FNF代码。开发无需了解FNF背后的配置细节就能利用FNF提供的`wait`和`foreach`快速开发业务。

## 快速开始

用两个常见的业务场景来说明fnfig的使用。

### 定期创建ECS镜像

生产环境使用的ECS镜像如果长时间不更新会存在很多安全漏洞，每次手动更新非常繁琐。脚本化后自动执行的时间很长，且大部分时间都是在等待ECS启动/停止、cloud init、快照创建，非常适合放在FNF上运行。

创建镜像的代码逻辑：

1. 使用最近Ubuntu镜像创建一台ECS。创建时传入cloud init脚本，用于安装生产环境所需组件，并使用`apt upgrade`更新最新安全补丁
2. 等待10秒，因为实例刚创建好时为Pending状态，该状态下不能做任何操作
3. 启动ECS并等待其状态为Running，耗时大约1分钟
4. 等待cloud init执行完成，耗时大约20分钟（视网络情况而定）
5. 停止ECS并等待其状态为Stopped，耗时大约1分钟
6. 创建快照并等待其完成，耗时大约20分钟
7. 创建快照
8. 删除创建的ECS


使用fnfig开发对应的代码只需要三步：

一，创建FIG描述文件`main.fig`

```
mkdir setup-image

cd setup-image

cat <<EOF > main.fig
create_ecs
wait 10
start_ecs
wait 10 until check_ecs_running
wait 60 until check_cloud_init_completed
stop_ecs
wait 10 until check_ecs_stopped
create_snapshot
wait 60 until check_snapshot_accomplished
create_image
delete_ecs
EOF
```

二，生成代码框架

执行命令：

```
python3 /path-of-fnfig/fnfig.py init main.fig
```

`fnfig.py`根据fig文件生成代码和测试框架。

`fnfig.py`生成`main.py`的骨架：

```
# import fig_utils


def initializer(_context): pass


def create_ecs(args): return args


def start_ecs(args): return args


def check_ecs_running(args): return True


def check_cloud_init_completed(args): return True


def stop_ecs(args): return args


def check_ecs_stopped(args): return True


def create_snapshot(args): return args


def check_snapshot_accomplished(args): return True


def create_image(args): return args


def delete_ecs(args): return args
```

其中`initializer`方法和FC中的`initializer`方法功能一样，如果不需要保持默认就好。

`create_ecs`、`start_ecs`、`stop_ecs`、`create_snapshot`、`create_image`、`delete_ecs`这6个方法需要用户实现对应的逻辑。`create_ecs`方法的入参`args`为启动FNF输入的参数，如果没有则为一个空字典，其余方法的入参为上一个访问的返回参数。即如果`create_ecs`返回`"yes"`，那么`start_ecs`的入参即为`"yes"`。fnfig推荐的方式如骨架中所示，每个方法都将`args`传递下去，这样后面的方法也能拿到前面方法的返回值。

`check_ecs_running`、`check_cloud_init_completed`、`check_ecs_stopped`、`check_snapshot_accomplished`这4个方法是`wait until`语句定义的方法，这些方法需要返回一个布尔值，如果其返回`False`，程序会等待定义的秒数，直到其返回`True`。


三，实现业务代码

编辑`main.py`实现自己的业务逻辑。

```
import datetime

ecs_client = None


def initializer(context):
    global ecs_client
    ecs_client = new_ecs_client(context)


def create_ecs(result):
    cloud_init_data = "some cloud init scripts"
    instance_id = ecs_client.create_ecs(cloud_init_data)
    result['instanceId'] = instance_id
    return result


def check_ecs_stopped(result):
    return ecs_client.get_instance(result['instanceId'])['Status'] == "STOPPED"


def start_ecs(result):
    ecs_client.start(result['instanceId'])
    return result


def check_ecs_running(result):
    return ecs_client.get_instance(result['instanceId'])['Status'] == "RUNNING"


def check_cloud_init_completed(result):
    return ecs_client.get_cloud_init_status(result['instanceId']).get('Completed', False)


def stop_ecs(result):
    ecs_client.stop(result['instanceId'])
    return result


def create_snapshot(result):
    snapshot_name = f"base-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    ecs_client.create_system_snapshot(result['instanceId'], snapshot_name)
    result['snapshotName'] = snapshot_name
    return result


def check_snapshot_accomplished(result):
    return ecs_client.get_snapshot(result['snapshotName'])['Status'] == "accomplished"


def create_image(result):
    snapshot_name = result['snapshotName']
    image_name = f"image-{snapshot_name}"
    ecs_client.create_image_by_snapshot(snapshot_name, image_name)
    return result


def delete_ecs(result):
    ecs_client.delete_ecs(result['instanceId'])
    return result
```


#### 测试代码

fnfig同样提供了一个测试框架，用以测试编写的业务代码。`fnfig.py`生成了测试文件`test.py`和`test.sh`。

当代码骨架刚被生成出来时，执行`bash test.sh`可测试`main.py`是否有问题。填入了业务逻辑后，可能需要对某些方法进行mock才能运行测试。

`test.py`中提供了一些mock的代码：

```
import fig_runner
import main
from fig_utils import FakeFDL, FakeResponder, Struct


if __name__ == "__main__":
    fig_runner._initializer_runner()

    # mock example
    # def es_post(x):
    #     print('post to es:', x)
    #     return Struct(status_code=200)
    # main.es_client = FakeResponder({'post': es_post})

    FakeFDL(fig_runner._handler, {}, {}).run()
```

使用`FakeResponder`和`Struct`来测试最终的业务代码：

```
import fig_runner
import main
from fig_utils import FakeFDL, FakeResponder, Struct


if __name__ == "__main__":
    fig_runner._initializer_runner()

    main.ecs_client = FakeResponder({
        'get_instance': [
            {'Status': "STOPPED"},
            {'Status': "RUNNING"},
            {'Status': "RUNNING"},
            {'Status': "STOPPED"},
        ],
        'get_cloud_init_status': [
            {'Completed': False},
            {'Completed': True}
        ],
        'get_snapshot': [
            {'Status': 'progressing', 'Progress': '10%'},
            {'Status': 'accomplished', 'Progress': '100%'}
        ],
        'create_ecs': ['the_instanceid'],
        'start': [{}],
        'stop': [{}],
        'create_system_snapshot': [{}],
        'create_image_by_snapshot': [{}],
        'delete_ecs': [{}],
    })

    FakeFDL(fig_runner._handler, {}, {}).run()
```

运行测试

```
bash test.sh
```


### 图片批量添加水印

OSS中多张图片需要添加水印，由于FC最长执行时间只有十分钟，在一个FC中处理可能会超时。推荐的做法是使用FNF的foreach来并行批量调用FC，每个FC只处理一张图片。

代码逻辑：

1. 从OSS获取需要添加水印的图片地址
2. 并行启动多个FC，分别将不同的图片地址传给每个FC
3. FC获取图片，添加水印后将新的图片传入OSS，返回水印图片地址。添加失败（如格式错误）则返回`None`
4. 待所有FC执行完成拿到所有水印图片地址，过滤失败的图片后返回给调用方

使用fnfig创建项目：

一，创建FIG描述文件`main.fig`

```
mkdir add-watermarks

cd add-watermarks

cat <<EOF > main.fig
get_original_images_from_oss
foreach add_watermark
filter_results
EOF
```

二，生成代码框架

执行命令：

```
python3 /path-of-fnfig/fnfig.py init main.fig
```

`main.py`骨架：

```
# import fig_utils


def initializer(_context): pass


def get_original_images_from_oss(args): return args, []


def add_watermark(args, value): return value


def filter_results(args, values): return args
```

`get_original_images_from_oss`之后的`add_watermark`由于是foreach方法，所以`get_original_images_from_oss`需要额外返回一个列表用于map。而`add_watermark`则多了一个输入参数用于接受列表map后的元素，这里对应的就是图片地址，添加水印后返回新的地址。`filter_results`也多了一个输入参数`values`，它是所有FC返回的结果列表，也就是所有水印图片的地址。

三，实现业务代码

编辑`main.py`实现自己的业务逻辑。

```
import fig_utils


def initializer(_context):
    pass


def get_original_images_from_oss(args):
    image_keys = get_sub_keys_from_oss_key(args['oss_key'])
    if len(image_keys) == 0:
        return fig_utils.go_to_end([])

    return args, image_keys


def add_watermark(_args, image_key): 
    image = get_images_from_oss_key(image_key)

    try:
        watermark_image = add_watermark_by_pil(image)
        watermark_image_key = upload_file_to_oss(watermark_image)
    except Exception as e:
        print(f"error: {e}")
        watermark_image_key = None

    return watermark_image_key


def filter_results(_args, watermark_image_keys):
    return [key for key in watermark_image_keys if key is not None]
```

在`get_original_images_from_oss`方法中，判断了待处理的图片是否为空，如果为空就调用`fig_utils.go_to_end`直接返回。这是fnfig提供的一个helper，意味直接结束，不必执行后面的步骤。

这里不直接返回的话在功能上也是没有问题的，fnfig的foreach可以正确处理列表为空的情况。但直接返回可以减少一些FNF转换步骤，成本上更有优势。


#### 测试代码

`test.py`

```
import main
import fig_runner
from fig_utils import FakeFDL, FakeResponder, Struct


if __name__ == "__main__":
    fig_runner._initializer_runner()

    def fake_get_sub_keys_from_oss_key(_key):
        return ["image1_key", "image2_key"]
    main.get_sub_keys_from_oss_key = fake_get_sub_keys_from_oss_key

    def fake_get_images_from_oss_key(key):
        return key.replace("_key", "")
    main.get_images_from_oss_key = fake_get_images_from_oss_key

    def fake_add_watermark_by_pil(image):
        if image == 'image1':
            return 'watermark_image1'
        raise Exception("invalid image")
    main.add_watermark_by_pil = fake_add_watermark_by_pil

    def fake_upload_file_to_oss(image):
        return f"{image}_key"
    main.upload_file_to_oss = fake_upload_file_to_oss

    results = FakeFDL(fig_runner._handler, {'oss_key': 'oss_key'}, {}).run()
    assert results == ['watermark_image1_key']
```

运行测试

```
bash test.sh
```

## 部署FNF

fnfig提供了一键部署代码到FNF的工具。fnfig会生成一个包含代码包的资源编排（ROS）配置，然后调用阿里云命令行工具`aliyun`将ROS配置部署上线。

在使用fnfig部署前，需要[安装](https://help.aliyun.com/document_detail/121544.html?spm=a2c4g.11186623.6.546.43255d40iF5pPX)`aliyun`并完成[配置](https://help.aliyun.com/document_detail/121258.html?spm=a2c4g.11186623.6.550.3cdd3ae5UNmfSO)。

这里提供一个step by step的例子来演示fnfig如何将代码部署上线。

一，创建FIG描述文件`main.fig`

```
mkdir fnfig-demo

cd fnfig-demo

cat <<EOF > main.fig
init_x_y
wait 5
add_all_x
foreach add_x
remove_y
check_result
EOF
```

二，生成代码框架

```
python3 /path-of-fnfig/fnfig.py init main.fig
```

三，编辑`main.py`实现业务代码

```
def initializer(_context):
    pass


def init_x_y(_):
    return {'x': 9, 'y': 12}


def add_all_x(args):
    return args, [1, 2, 3, 4, 5]


def add_x(args, value):
    return value + args['x']


def remove_y(args, values):
    result = [value for value in values if value != args['y']]
    args['result'] = result
    return args


def check_result(args):
    assert args['result'] == [10, 11, 13, 14]
    print('ok!')
    return args
```


 四，部署上线

 ```
python3 /path-of-fnfig/fnfig.py deploy main.fig \
        --account-alias ${account_alias} \
        --arn-role ${arn_role} \
        --region cn-hangzhou \
        --interval 60 \
        --fc-timeout 30 \
        --fnf-timeout 60 \
        --fc-memory 128 \
        --fc-service ${fc_service}
 ```

`deploy`支持多个配置参数：

```
  --account-alias 企业别名。必填
  --arn-role ARN角色，授予FNF执行任务所需权限。必填 \
  --region 阿里云区域。选填，默认为 cn-hangzhou
  --interval FNF定时器触发周期，单位分。选填，默认为不设置定时器
  --fc-timeout FC超时时间，单位秒。选填，默认为 30 \
  --fnf-timeout FNF超时时间，单位秒。选填，默认为 60 \
  --fc-memory FC内存，单位M。选填，默认为 128 \
  --fc-service FC服务组。必填。
```

`--account-alias`、`--arn-role`及`--fc-service`为必填，其中`--arn-role`和`--fc-service`需在控制台提前创建。
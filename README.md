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
python3 /path-of-fnfig/fnfig.py main.fig
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
# import fig_utils
import datetime

ecs_client = None


def initializer(context):
    global ecs_client
    ecs_client = new_ecs_client(context)


def create_ecs(result):
    instance_id = ecs_client.create_ecs()
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

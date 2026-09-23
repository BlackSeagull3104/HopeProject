"""Desktop product routes with application-managed storage and explicit exports."""
from .settings import Settings
from .library import Library
from .ocr import OCRJobs
from .export_documents import export_pages
from .application import ArchiveError


def configure_library(service):
    if service.preferences.read()['exportConfigured']:
        from .archive_workflow import migrate_legacy
        backup = service.preferences.backup()
        migration = migrate_legacy(service.preferences.home, backup)
        service.migration_warning = '部分旧备份与当前备份存在差异，未覆盖任何文件；原资料仍保留。' if migration['conflicts'] else ''
        service.library = Library(service.preferences.home, backup)
        return migration
    return {'copied':0,'conflicts':0}


def run_capsules(service, token, identity, user):
    from .media import localize_refs
    try:
        offset = 0
        while True:
            service.update(identity, stage=f'正在归档已开启胶囊…已处理 {offset} 条')
            result = service.capsule_request('/capsules/list', {'status':'opened','offset':offset,
                'outputDir':str(service.library.account_root(user['userId']))}, token)
            archive = user['capsule_archive']
            for item in result['items']:
                if item['content_available']:
                    detail = service.capsule_request('/capsules/detail', {'id':item['id']}, token)
                    if detail['content_available']:
                        stats = localize_refs(archive.entries[item['id']]['media'], archive.root/'archive')
                        if stats['failed']: service.update(identity, mediaWarning='部分媒体未保存，请稍后更新重试。')
            offset = result['nextOffset']
            if not result['hasMore']: break
        service.update(identity, state='completed',stage='已更新本地已开启胶囊归档。')
    except Exception:
        service.update(identity, state='failed',stage='胶囊归档未完成，请检查网络或登录状态后重试；已保存内容保留。')


def dispatch(service, method, path, body, token):
    from .local_api import RequestError, fields
    from . import search, ai, ai_assistant
    with service.lock:
        if not hasattr(service, 'preferences'):
            service.preferences = Settings(getattr(service, 'home', None))
            service.library = Library(service.preferences.home)
            service.ocr_jobs = OCRJobs()
            configure_library(service)
    if method != 'POST' or not isinstance(body, dict): raise RequestError(400, '请求格式无效。')
    try:
        if path == '/settings/read':
            fields(body, [])
            return dict(service.preferences.read(),migrationWarning=getattr(service,'migration_warning',''))
        if path == '/settings/save':
            fields(body, ['exportRoot'])
            with service.lock:
                if any(j['state']=='running' for j in service.jobs.values()):
                    raise RequestError(409,'归档进行中，请完成后再更改目录。')
                result=service.preferences.save(body['exportRoot'])
                migration=configure_library(service)
                service.preferences.destination('diaries')
                return dict(result,migration=migration,migrationWarning=getattr(service,'migration_warning',''))
        if path == '/ocr/start':
            if set(body) != {'images'}: raise ValueError('图片请求格式无效。')
            return service.ocr_jobs.start(body['images'])
        if path in ('/ocr/status', '/ocr/cancel'):
            fields(body, ['jobId'])
            return service.ocr_jobs.status(body['jobId']) if path.endswith('status') else service.ocr_jobs.cancel(body['jobId'])
        if path == '/ocr/export':
            if set(body) != {'pages', 'format'}: raise ValueError('导出请求格式无效。')
            return export_pages(body['pages'], service.preferences.destination('ocr'), body['format'])
        user = service.session(token) if token else None
        user_id = user['userId'] if user else None
        if path == '/library/preview':
            return service.dispatch('POST','/diaries/preview',body,token)
        if path == '/library/media':
            fields(body, ['key'])
            return service.library.media(body['key'], user_id)
        if path.startswith('/library/ai/'):
            with service.lock:
                if service.ai_settings is None: service.ai_settings = ai.AISettings()
            root = service.library.account_root(user_id) if user_id else service.library.root
            assistant = ai_assistant.DiaryAssistant(search.SearchIndex(root, service.search_cache), service.ai_settings)
            if path.endswith('/status'):
                fields(body, [])
                return assistant.status()
            if path.endswith('/ask'):
                return assistant.ask(body)
            raise RequestError(404, '接口不存在。')
        if path.startswith('/library/search/'):
            root = service.library.account_root(user_id) if user_id else service.library.root
            index = search.SearchIndex(root, service.search_cache)
            if path.endswith('/rebuild'):
                fields(body, [])
                return index.sync(rebuild=True)
            if path.endswith('/detail'):
                fields(body, ['id'])
                return index.detail(body['id'])
            fields(body, ['query'], ['beginDate','endDate','diaryType','contentType','offset'])
            return index.query(body['query'], body.get('beginDate',''), body.get('endDate',''), body.get('diaryType','all'), body.get('contentType','all'), body.get('offset',0))
        if path == '/library/download':
            return dispatch(service,method,'/library/archive',dict(body,formats=['markdown']),token)
        if path == '/library/archive':
            from .archive_workflow import run, formats_for
            from .application import validate_date_range
            from .diary_types import filter_value
            import secrets
            user=service.session(token)
            fields(body,['beginDate','endDate'],['diaryType','formats'])
            validate_date_range(body['beginDate'],body['endDate'])
            filter_value(body.get('diaryType','all'))
            formats_for(body.get('formats'))
            with service.lock:
                output=service.preferences.destination('diaries')
                if any(j['state']=='running' for j in service.jobs.values()): raise RequestError(409,'已有归档任务正在进行。')
                if len(service.jobs)>=100: service.jobs.pop(next(iter(service.jobs)))
                identity=secrets.token_urlsafe(16)
                service.jobs[identity]={'owner':token,'state':'running','stage':'正在准备归档…','kind':'archive'}
                service.pool.submit(run,service,identity,dict(body),user['userId'],service.library,output)
            return {'jobId':identity}
        if path == '/library/export':
            fields(body, ['beginDate','endDate','format'], ['diaryType'])
            return service.library.export(body, service.preferences.destination('diaries'), user_id)
        if path == '/library/capsules':
            fields(body, [])
            return service.library.browse_capsules(user_id)
        if path == '/library/capsules/update':
            fields(body, [])
            user = service.session(token)
            service.preferences.backup()
            import secrets
            with service.lock:
                if any(j['state']=='running' for j in service.jobs.values()):
                    raise RequestError(409,'已有归档任务正在进行。')
                if len(service.jobs)>=100: service.jobs.pop(next(iter(service.jobs)))
                identity=secrets.token_urlsafe(16)
                service.jobs[identity]={'owner':token,'state':'running','stage':'正在准备已开启胶囊归档…','kind':'capsules'}
                service.pool.submit(run_capsules,service,token,identity,user)
            return {'jobId':identity}
        if path == '/library/capsules/export':
            fields(body, ['format'], ['ids'])
            return service.library.export_capsules(body, service.preferences.destination('capsules'), user_id)
    except (ValueError, OSError, search.SearchError, ai.AIError, ai_assistant.AssistantError, ArchiveError) as exc:
        if isinstance(exc, OSError): raise RequestError(400, '无法读写本地文件，请检查文件夹权限。') from None
        raise RequestError(400, str(exc)) from None
    raise RequestError(404, '接口不存在。')

# -*- coding: utf-8 -*-
"""Окна сообщений кнопок HVAC в общем стиле (hvac_ui): информация, предупреждение, ошибка, вопрос «да/нет».

Вместо стандартных диалогов pyRevit и окна вывода. Что умеет окно:
  * цветная метка вида сообщения («Информация», «Внимание», «Ошибка»), заголовок и пояснение;
  * список элементов: каждый — ссылка с названием и id; клик просто выделяет элемент в модели (вид не двигается, окон и сообщений нет);
  * подробности (например, traceback) в поле, из которого можно выделять и копировать текст;
  * кнопка «Копировать» — весь текст сообщения целиком в буфер обмена;
  * кнопка «Открыть журнал» — файл журнала кнопки;
  * окно перетаскивается; Enter и Esc закрывают.

Подключение в кнопке (после импорта pyrevit):

    hvac_dialog.configure(forms=forms, select=lambda i: hvac_revit.select_element(uidoc, DB, List, i),
                          log_path=hvac_log.log_path)
    hvac_dialog.warn(u'Заголовок\\nпояснение', title=u'FlexTail', elements=[(u'Воздуховоды · id 1', 1)])

Если окно создать не удалось, сообщение показывается стандартным диалогом pyRevit (forms.alert).
Совместимо с IronPython 3.4 и CPython (без f-строк)."""
import os
import re

import hvac_ui

INFO = 'info'
WARNING = 'warning'
ERROR = 'error'

RU = {
    'kind_info': u'Информация', 'kind_warning': u'Внимание', 'kind_error': u'Ошибка',
    'copy': u'Копировать', 'log': u'Открыть журнал', 'close': u'Закрыть',
    'elements': u'Элементы — нажмите, чтобы выделить в модели:', 'select_tip': u'Выделить в модели',
    'details': u'Подробности:', 'plain_elements': u'Элементы:', 'plain_log': u'Журнал: {0}',
    'more': u'…и ещё {0} (полный список — по кнопке «Копировать»)',
    'copied': u'Сообщение скопировано в буфер обмена.', 'copy_fail': u'Не удалось скопировать в буфер обмена.',
    'selected': u'Элемент выделен в модели.', 'select_fail': u'Не удалось выделить элемент: возможно, он удалён.',
    'log_opened': u'Журнал открыт.', 'log_fail': u'Не удалось открыть журнал: {0}'}
UK = {
    'kind_info': u'Інформація', 'kind_warning': u'Увага', 'kind_error': u'Помилка',
    'copy': u'Копіювати', 'log': u'Відкрити журнал', 'close': u'Закрити',
    'elements': u'Елементи — натисніть, щоб виділити в моделі:', 'select_tip': u'Виділити в моделі',
    'details': u'Подробиці:', 'plain_elements': u'Елементи:', 'plain_log': u'Журнал: {0}',
    'more': u'…і ще {0} (повний список — кнопкою «Копіювати»)',
    'copied': u'Повідомлення скопійовано в буфер обміну.', 'copy_fail': u'Не вдалося скопіювати в буфер обміну.',
    'selected': u'Елемент виділено в моделі.', 'select_fail': u'Не вдалося виділити елемент: можливо, його видалено.',
    'log_opened': u'Журнал відкрито.', 'log_fail': u'Не вдалося відкрити журнал: {0}'}
# (фон метки, цвет текста метки); контраст не ниже 4,5:1
COLORS = {INFO: (u'#5BB6E8', hvac_ui.NAVY), WARNING: (hvac_ui.AMBER, hvac_ui.NAVY), ERROR: (u'#B03A3A', u'#FFFFFF')}
MAX_ELEMENTS = 8                   # столько ссылок-элементов показываем, остальное — строкой «и ещё N»
WIDTH = 480
WIDTH_WITH_DETAILS = 580

_CTX = {'forms': None, 'select': None, 'log_path': None, 'strings': RU}
_LOG_LINE = re.compile(u'\\n*Журнал: ?([^\\n]+)\\s*$')


def S(key):
    return _CTX['strings'][key]


def configure(forms=None, select=None, log_path=None, strings=None):
    """forms — pyrevit.forms; select(id) — выделить и показать элемент в модели; log_path() — путь журнала кнопки;
    strings — тексты окна (RU по умолчанию, UK — украинские)."""
    for key, value in (('forms', forms), ('select', select), ('log_path', log_path), ('strings', strings)):
        if value is not None:
            _CTX[key] = value


class Message(object):
    def __init__(self, kind=INFO, title=u'HVAC', heading=u'', body=u'', details=u'', elements=None, log=u'',
                 kind_label=None, confirm=None, tag=u''):
        self.kind = kind if kind in COLORS else INFO
        self.title = title
        self.heading = heading or u''
        self.body = body or u''
        self.details = details or u''
        self.elements = list(elements or [])
        self.log = log or u''
        self.kind_label = kind_label or S('kind_' + self.kind)
        self.confirm = confirm                      # None или (текст «да», текст «нет»)
        self.tag = tag                              # метка вида окна: «warnings» — замечания после работы


def split_log(text):
    """«…\\n\\nЖурнал: путь» → (текст без этой строки, путь). Путь становится кнопкой «Открыть журнал»."""
    match = _LOG_LINE.search(text)
    if not match:
        return text, u''
    return text[:match.start()].rstrip(), match.group(1).strip()


def split_text(text):
    """Текст сообщения → (заголовок, пояснение): первая строка — заголовок, остальное — пояснение."""
    lines = text.strip().split(u'\n')
    heading = lines[0].strip()
    body = u'\n'.join(lines[1:]).strip()
    return heading, body


def make_message(kind, text, title, **kw):
    """Собрать Message из обычного текста (как раньше передавали в forms.alert). Явные heading/body имеют приоритет."""
    log = kw.pop('log', None)
    heading = kw.pop('heading', None)
    body = kw.pop('body', None)
    if heading is None and body is None:
        text, found = split_log(text or u'')
        heading, body = split_text(text) if text.strip() else (u'', u'')
        log = found if log is None else log
    if log is True:                                  # log=True — путь журнала этой кнопки
        getter = _CTX['log_path']
        log = getter() if getter is not None else u''
    elif log is None:
        log = u''
    return Message(kind=kind, title=title, heading=heading or u'', body=body or u'', log=log, **kw)


def plain_text(msg):
    """Всё сообщение простым текстом — для буфера обмена и стандартного диалога."""
    lines = [u'[{0}] {1}'.format(msg.kind_label, msg.title)]
    if msg.heading:
        lines.append(msg.heading)
    if msg.body:
        lines.append(msg.body)
    if msg.details:
        lines.extend((u'', msg.details))
    if msg.elements:
        lines.append(u'')
        lines.append(S('plain_elements'))
        lines.extend(u'  ' + label for label, _eid in msg.elements)
    if msg.log:
        lines.append(u'')
        lines.append(S('plain_log').format(msg.log))
    return u'\n'.join(lines)


def element_label(category, name, element_id):
    """Подпись ссылки: «Воздуховоды «Тип 1» · id 123456»."""
    parts = [category]
    if name:
        parts.append(u'«{0}»'.format(name))
    return u'{0} · id {1}'.format(u' '.join(p for p in parts if p), element_id)


def build_xaml(msg):
    """XAML окна сообщения. Тексты в него не вставляются (их записывает код), поэтому экранировать нечего."""
    bg, fg = COLORS[msg.kind]
    shown = msg.elements[:MAX_ELEMENTS]
    parts = [
        u'      <Border Background="%s" CornerRadius="10" Padding="12,2" HorizontalAlignment="Left" Margin="0,0,0,10">' % bg,
        u'        <TextBlock x:Name="kind_text" FontWeight="Bold" FontSize="13" Foreground="%s"/>' % fg,
        u'      </Border>',
        u'      <TextBlock x:Name="heading" Style="{StaticResource Label}" FontSize="16" Margin="0,0,0,6"/>',
        u'      <TextBlock x:Name="body" TextWrapping="Wrap" Foreground="%s" Margin="0,0,0,10"/>' % hvac_ui.INK_SOFT]
    if shown:
        parts.append(hvac_ui.label(S('elements'), u'0,2,0,4'))
        for i in range(len(shown)):
            parts.append(u'      <Button x:Name="elem%d" Style="{StaticResource Link}" HorizontalAlignment="Left" Margin="0,0,0,2"/>' % i)
        if len(msg.elements) > MAX_ELEMENTS:
            parts.append(u'      <TextBlock x:Name="more" Style="{StaticResource Muted}" Margin="0,2,0,0"/>')
    if msg.details:
        parts.append(hvac_ui.label(S('details'), u'0,8,0,4'))
        parts.append(u'      <TextBox x:Name="details" IsReadOnly="True" TextWrapping="Wrap" AcceptsReturn="True" '
                     u'VerticalScrollBarVisibility="Auto" MaxHeight="190" FontFamily="Consolas" FontSize="12"/>')
    parts.append(u'      <TextBlock x:Name="status" Style="{StaticResource Muted}" Margin="0,8,0,0" MinHeight="20"/>')
    left = [u'        <Button x:Name="copy_btn" Content="%s" Margin="0,0,8,0"/>' % hvac_ui.escape(S('copy'))]
    if msg.log:
        left.append(u'        <Button x:Name="log_btn" Content="%s" Margin="0,0,8,0"/>' % hvac_ui.escape(S('log')))
    if msg.confirm:
        right = (u'        <Button x:Name="yes_btn" Content="" MinWidth="96" Margin="0,0,8,0" IsDefault="True"/>\n'
                 u'        <Button x:Name="no_btn" Content="" MinWidth="96" IsCancel="True"/>')
    else:
        right = (u'        <Button x:Name="close_btn" Content="%s" MinWidth="96" IsDefault="True" IsCancel="True"/>'
                 % hvac_ui.escape(S('close')))
    parts.append(u'      <Grid Margin="0,14,0,0">')
    parts.append(u'        <StackPanel Orientation="Horizontal" HorizontalAlignment="Left">')
    parts.extend(left)
    parts.append(u'        </StackPanel>')
    parts.append(u'        <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">')
    parts.append(right)
    parts.append(u'        </StackPanel>')
    parts.append(u'      </Grid>')
    width = WIDTH_WITH_DETAILS if msg.details else WIDTH
    return hvac_ui.window_xaml(msg.title, width, u'\n'.join(parts))


# ---------- действия окна (подменяются в тестах) ----------

def copy_to_clipboard(text):
    """Положить текст в буфер обмена. True — получилось."""
    try:
        from System.Windows import Clipboard
    except Exception:
        return False
    for attempt in (lambda: Clipboard.SetText(text), lambda: Clipboard.SetDataObject(text, True)):
        try:
            attempt()
            return True
        except Exception:
            continue
    return False


def open_path(path):
    """Открыть файл (или папку, если файла нет) программой по умолчанию. True — получилось."""
    target = path if os.path.exists(path) else os.path.dirname(path)
    if not target:
        return False
    try:
        os.startfile(target)
        return True
    except Exception:
        pass
    try:
        from System.Diagnostics import Process
        Process.Start(target)
        return True
    except Exception:
        return False


def select_element(element_id):
    """Выделить элемент в модели и показать его. True — получилось."""
    select = _CTX['select']
    if select is None:
        return False
    try:
        select(element_id)
        return True
    except Exception:
        return False


# ---------- показ ----------

def _show_window(forms, msg):
    xaml = build_xaml(msg)
    shown = msg.elements[:MAX_ELEMENTS]

    class MessageWindow(forms.WPFWindow):
        def __init__(self):
            forms.WPFWindow.__init__(self, xaml, literal_string=True)
            hvac_ui.enable_drag(self)
            self.answer = False
            hvac_ui.set_title(self, msg.title)
            hvac_ui.set_text(self, 'kind_text', msg.kind_label)
            hvac_ui.set_text(self, 'heading', msg.heading)
            hvac_ui.set_text(self, 'body', msg.body)
            if msg.details:
                hvac_ui.set_text(self, 'details', msg.details)
            for i, (label, element_id) in enumerate(shown):
                button = self.FindName('elem%d' % i)
                button.Content = label
                button.Click += self.element_handler(element_id)
            if len(msg.elements) > MAX_ELEMENTS:
                hvac_ui.set_text(self, 'more', S('more').format(len(msg.elements) - MAX_ELEMENTS))
            self.FindName('copy_btn').Click += self.on_copy
            if msg.log:
                self.FindName('log_btn').Click += self.on_log
            if msg.confirm:
                yes, no = self.FindName('yes_btn'), self.FindName('no_btn')
                yes.Content, no.Content = msg.confirm
                yes.Click += self.on_yes
                no.Click += self.on_close
            else:
                self.FindName('close_btn').Click += self.on_close

        def status(self, text):
            hvac_ui.set_text(self, 'status', text)

        def element_handler(self, element_id):
            def handler(sender, args):
                if not select_element(element_id):            # получилось — молча: просто выделили элемент
                    self.status(S('select_fail'))
            return handler

        def on_copy(self, sender, args):
            ok = copy_to_clipboard(plain_text(msg))
            self.status(S('copied') if ok else S('copy_fail'))

        def on_log(self, sender, args):
            ok = open_path(msg.log)
            self.status(S('log_opened') if ok else S('log_fail').format(msg.log))

        def on_yes(self, sender, args):
            self.answer = True
            self.Close()

        def on_close(self, sender, args):
            self.Close()

    window = MessageWindow()
    window.ShowDialog()
    return window.answer if msg.confirm else True


def _fallback(forms, msg):
    """Стандартный диалог pyRevit, если своё окно создать не удалось."""
    text = plain_text(msg)
    if msg.confirm:
        return bool(forms.alert(text, title=msg.title, yes=True, no=True))
    forms.alert(text, title=msg.title)
    return True


def show(msg):
    """Показать сообщение. Вопрос — возвращает True/False; остальное — True."""
    forms = _CTX['forms']
    if forms is None:
        raise RuntimeError('hvac_dialog.configure(forms=...) не вызывали')
    try:
        return _show_window(forms, msg)
    except Exception:
        try:
            import hvac_log
            hvac_log.log_exception('HVAC', u'окно сообщения не удалось, беру стандартный диалог')
        except Exception:
            pass
        return _fallback(forms, msg)


def info(text=u'', title=u'HVAC', **kw):
    return show(make_message(INFO, text, title, **kw))


def warn(text=u'', title=u'HVAC', **kw):
    return show(make_message(WARNING, text, title, **kw))


def error(text=u'', title=u'HVAC', **kw):
    kw.setdefault('log', True)                       # у ошибки всегда есть кнопка «Открыть журнал»
    return show(make_message(ERROR, text, title, **kw))


def confirm(text=u'', title=u'HVAC', yes=u'Да', no=u'Нет', **kw):
    kw.setdefault('kind', WARNING)
    kind = kw.pop('kind')
    return show(make_message(kind, text, title, confirm=(yes, no), **kw))

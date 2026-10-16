# -*- coding: utf-8 -*-
"""Общий вид окон кнопок HVAC — как на слайдах презентации: тёмно-синяя шапка, светлый фон, поля с рамкой и
скруглёнными углами, плашки-чипы, основная кнопка (OK / Сохранить) залита тёмно-синим, вторая — с рамкой.

Модуль только собирает XAML-строки и не зависит от Revit. Каждое окно собирается так:

    xaml = hvac_ui.window_xaml(u'Заголовок', 420, тело_окна_в_XAML)

Стили (кнопки, поля, списки) заданы неявно в ресурсах окна, поэтому обычные Button / TextBox / ComboBox в теле окна
уже выглядят правильно. Именованные стили: Label (подпись над полем), Muted (приглушённый текст), Chip (кнопка-чип),
ChipToggle (переключаемый чип). Совместимо с IronPython 3.4 и CPython (без f-строк)."""

NAVY = u'#14213D'
PAPER = u'#FBFAF6'
FIELD = u'#FFFDF8'
SAND = u'#F3F0E8'
SAND_LINE = u'#DDD8CB'
AMBER = u'#F2A93B'
AMBER_SOFT = u'#FBE3B4'
STEEL = u'#9AA6B8'
MUTED = u'#5B6677'
INK_SOFT = u'#3A4660'
LIGHT = u'#EAF0F8'

# Имена, которые окна ожидают найти (FindName): заголовок в шапке и блок «найденные данные».
TITLE_NAME = u'title_text'
TITLE_BAR_NAME = u'title_bar'
INFO_TITLE_NAME = u'info_title'
INFO_NAME = u'info'

_RESOURCES = u'''
    <Style TargetType="Button">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="Padding" Value="16,6"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="bd" Background="@PAPER@" BorderBrush="@NAVY@" BorderThickness="2" CornerRadius="6"
                    Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="@SAND@"/>
              </Trigger>
              <Trigger Property="IsDefault" Value="True">
                <Setter TargetName="bd" Property="Background" Value="@NAVY@"/>
                <Setter Property="Foreground" Value="@LIGHT@"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Opacity" Value="0.5"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="Chip" TargetType="Button">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="Padding" Value="8,5"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="bd" Background="@FIELD@" BorderBrush="@STEEL@" BorderThickness="2" CornerRadius="6"
                    Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="@AMBER_SOFT@"/>
                <Setter TargetName="bd" Property="BorderBrush" Value="@NAVY@"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="ChipToggle" TargetType="ToggleButton">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="Padding" Value="12,6"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ToggleButton">
            <Border x:Name="bd" Background="@FIELD@" BorderBrush="@NAVY@" BorderThickness="2" CornerRadius="8"
                    Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="@AMBER_SOFT@"/>
              </Trigger>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="bd" Property="Background" Value="@NAVY@"/>
                <Setter Property="Foreground" Value="@LIGHT@"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style TargetType="TextBox">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="Padding" Value="8,5"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="TextBox">
            <Border Background="@FIELD@" BorderBrush="@NAVY@" BorderThickness="2" CornerRadius="6">
              <ScrollViewer x:Name="PART_ContentHost" Margin="{TemplateBinding Padding}"/>
            </Border>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style TargetType="ComboBoxItem">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ComboBoxItem">
            <Border x:Name="bd" Background="Transparent" Padding="10,6">
              <ContentPresenter/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsHighlighted" Value="True">
                <Setter TargetName="bd" Property="Background" Value="@AMBER_SOFT@"/>
              </Trigger>
              <Trigger Property="IsSelected" Value="True">
                <Setter Property="FontWeight" Value="SemiBold"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style TargetType="ComboBox">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ComboBox">
            <Grid>
              <ToggleButton x:Name="tb" Focusable="False" ClickMode="Press"
                            IsChecked="{Binding Path=IsDropDownOpen, Mode=TwoWay, RelativeSource={RelativeSource TemplatedParent}}">
                <ToggleButton.Template>
                  <ControlTemplate TargetType="ToggleButton">
                    <Border Background="@FIELD@" BorderBrush="@NAVY@" BorderThickness="2" CornerRadius="6" MinHeight="34">
                      <Path HorizontalAlignment="Right" VerticalAlignment="Center" Margin="0,0,10,0"
                            Data="M 0 0 L 5 6 L 10 0 Z" Fill="@NAVY@"/>
                    </Border>
                  </ControlTemplate>
                </ToggleButton.Template>
              </ToggleButton>
              <ContentPresenter IsHitTestVisible="False" Margin="10,0,30,0" VerticalAlignment="Center"
                                HorizontalAlignment="Left" Content="{TemplateBinding SelectionBoxItem}"
                                ContentTemplate="{TemplateBinding SelectionBoxItemTemplate}"/>
              <Popup Placement="Bottom" IsOpen="{TemplateBinding IsDropDownOpen}" AllowsTransparency="True"
                     Focusable="False">
                <Border MinWidth="{Binding ActualWidth, ElementName=tb}" MaxHeight="{TemplateBinding MaxDropDownHeight}"
                        Background="@FIELD@" BorderBrush="@STEEL@" BorderThickness="2" CornerRadius="6" Margin="0,2,0,0">
                  <ScrollViewer>
                    <StackPanel IsItemsHost="True" KeyboardNavigation.DirectionalNavigation="Contained"/>
                  </ScrollViewer>
                </Border>
              </Popup>
            </Grid>
            <ControlTemplate.Triggers>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Opacity" Value="0.5"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style TargetType="CheckBox">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="VerticalContentAlignment" Value="Center"/>
    </Style>
    <Style x:Key="Label" TargetType="TextBlock">
      <Setter Property="Foreground" Value="@NAVY@"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="TextWrapping" Value="Wrap"/>
      <Setter Property="Margin" Value="0,0,0,4"/>
    </Style>
    <Style x:Key="Muted" TargetType="TextBlock">
      <Setter Property="Foreground" Value="@MUTED@"/>
      <Setter Property="TextWrapping" Value="Wrap"/>
    </Style>
'''

_WINDOW = u'''<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="@TITLE@" Width="@WIDTH@" SizeToContent="Height" WindowStartupLocation="CenterScreen"
        WindowStyle="None" ResizeMode="NoResize" ShowInTaskbar="False" Topmost="True"
        Background="@PAPER@" BorderBrush="@NAVY@" BorderThickness="2"
        FontFamily="Segoe UI" FontSize="14" Foreground="@NAVY@" SnapsToDevicePixels="True">
  <Window.Resources>@RESOURCES@  </Window.Resources>
  <DockPanel>
    <Border x:Name="title_bar" DockPanel.Dock="Top" Background="@NAVY@" Padding="14,9">
      <TextBlock x:Name="title_text" Text="@TITLE@" Foreground="@LIGHT@" FontSize="15" FontWeight="SemiBold"/>
    </Border>
    <StackPanel Margin="16,14,16,16">
@BODY@
    </StackPanel>
  </DockPanel>
</Window>
'''

# Блок «найденные данные» над полями окна (диаметр, длина, тип…): заголовок и несколько строк.
INFO_XAML = u'''      <Border Background="@SAND@" BorderBrush="@SAND_LINE@" BorderThickness="1" CornerRadius="6"
              Padding="10,8" Margin="0,0,0,12">
        <StackPanel>
          <TextBlock x:Name="info_title" FontWeight="SemiBold" Margin="0,0,0,4"/>
          <TextBlock x:Name="info" TextWrapping="Wrap" Foreground="@INK_SOFT@"/>
        </StackPanel>
      </Border>'''

_COLORS = (u'NAVY', u'PAPER', u'FIELD', u'SAND', u'SAND_LINE', u'AMBER', u'AMBER_SOFT', u'STEEL', u'MUTED',
           u'INK_SOFT', u'LIGHT')


def _paint(text):
    for name in _COLORS:
        text = text.replace(u'@' + name + u'@', globals()[name])
    return text


def escape(text):
    """Экранирование для значений XML-атрибутов (заголовок окна и т.п.)."""
    return (text.replace(u'&', u'&amp;').replace(u'<', u'&lt;').replace(u'>', u'&gt;').replace(u'"', u'&quot;'))


def window_xaml(title, width, body):
    """Готовый XAML окна: шапка с заголовком, светлое тело, общие стили. body — XAML внутри StackPanel."""
    text = _WINDOW.replace(u'@RESOURCES@', _RESOURCES).replace(u'@BODY@', body)
    text = text.replace(u'@TITLE@', escape(title)).replace(u'@WIDTH@', str(int(width)))
    return _paint(text)


def info_block():
    """XAML блока «найденные данные» (имена info_title и info)."""
    return _paint(INFO_XAML)


def label(text, margin=u'0,0,0,4'):
    """Подпись над полем."""
    return u'      <TextBlock Style="{StaticResource Label}" Text="%s" Margin="%s"/>' % (escape(text), margin)


def buttons(ok_name, ok_text, cancel_name=u'cancel_btn', cancel_text=u'Отмена'):
    """Ряд кнопок справа: основная (по Enter, залита тёмно-синим) и «Отмена» (по Esc)."""
    return (u'      <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">\n'
            u'        <Button x:Name="%s" Content="%s" MinWidth="96" Margin="0,0,8,0" IsDefault="True"/>\n'
            u'        <Button x:Name="%s" Content="%s" MinWidth="96" IsCancel="True"/>\n'
            u'      </StackPanel>' % (ok_name, escape(ok_text), cancel_name, escape(cancel_text)))


def enable_drag(window):
    """Окно без системной рамки (WindowStyle=None) само не двигается: тащим его за любое место, где нет элемента
    управления (шапка, подписи, поля между ними). Вызывать после инициализации окна. True — обработчик подключён."""
    def on_mouse_down(sender, args):
        try:
            window.DragMove()                # бросает исключение, если кнопку уже отпустили — это не ошибка
        except Exception:
            pass
    try:
        window.MouseLeftButtonDown += on_mouse_down
        return True
    except Exception:
        return False


def set_title(window, text):
    """Заголовок окна: и системный (Title), и в нашей шапке. Ошибки шапки не критичны."""
    window.Title = text
    try:
        window.FindName(TITLE_NAME).Text = text
    except Exception:
        pass


def fill_info(window, title, text):
    """Заполнить блок «найденные данные» (если он есть в окне)."""
    try:
        window.FindName(INFO_TITLE_NAME).Text = title
        window.FindName(INFO_NAME).Text = text
    except Exception:
        pass


def size_text(label_text, has_shape=True):
    """«Ø200» → «Ø200 мм»; неизвестный размер («?») — без единиц."""
    return label_text + u' мм' if has_shape and label_text != u'?' else label_text

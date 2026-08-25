import io
from reportlab.pdfgen import canvas as C
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.lib import colors

def _make_pdf(title, client, rater, items, labels, instr):
    buf = io.BytesIO()
    c = C.Canvas(buf, pagesize=A4)
    w, h = A4
    M = 45  # margin

    def draw_header(page=1):
        c.setFont('Helvetica-Bold', 13)
        c.drawString(M, h - 44, title)
        c.setFont('Helvetica', 9)
        c.drawString(M, h - 60, f'Client: {client or "_________________________________"}   Date: _______________')
        c.drawString(M, h - 74, f'Rater / Respondent: {rater.capitalize()}')
        c.line(M, h - 80, w - M, h - 80)
        # Rating key box
        c.setFont('Helvetica-Bold', 8)
        c.drawString(M, h - 94, 'RATING KEY:')
        c.setFont('Helvetica', 8)
        key_x = M + 68
        for i, lbl in enumerate(labels):
            c.drawString(key_x, h - 94, f'{i} = {lbl}')
            key_x += (w - M - key_x - 10) / max(1, len(labels) - i - 1) if i < len(labels)-1 else 0
        # Column headers (numbers only)
        n = len(labels)
        col_w = 26
        cb_start = w - M - n * col_w
        c.setFont('Helvetica-Bold', 8)
        for i in range(n):
            cx = cb_start + i * col_w + col_w / 2
            c.drawCentredString(cx, h - 108, str(i))
        c.line(M, h - 112, w - M, h - 112)
        return h - 120  # starting y

    y = draw_header()
    n = len(labels)
    col_w = 26
    cb_start = w - M - n * col_w
    text_w = cb_start - M - 10

    c.setFont('Helvetica', 8.5)

    for idx, item in enumerate(items):
        text = f'{idx + 1}.  {item}'
        wrapped = simpleSplit(text, 'Helvetica', 8.5, text_w)
        row_h = max(18, len(wrapped) * 11 + 6)

        if y - row_h < 45:
            c.showPage()
            y = draw_header()
            c.setFont('Helvetica', 8.5)

        # Alternating row background
        if idx % 2 == 0:
            c.setFillColorRGB(0.97, 0.97, 0.97)
            c.rect(M, y - row_h + 4, w - 2 * M, row_h, fill=1, stroke=0)
            c.setFillColorRGB(0, 0, 0)

        # Question text (left side)
        ty = y - 1
        for line in wrapped:
            c.drawString(M + 4, ty, line)
            ty -= 11

        # AcroForm checkboxes (right side, centred in row)
        cb_y = y - row_h / 2 - 5
        for i in range(n):
            cx = cb_start + i * col_w + col_w / 2 - 6
            c.acroForm.checkbox(
                name=f'q{idx + 1}_opt{i}',
                x=cx,
                y=cb_y,
                size=12,
                checked=False,
                buttonStyle='check',
                borderStyle='solid',
                borderWidth=0.8,
                borderColor=colors.HexColor('#555555'),
                fillColor=colors.white,
                forceBorder=True
            )

        # Row separator line
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.line(M, y - row_h + 4, w - M, y - row_h + 4)
        c.setStrokeColorRGB(0, 0, 0)

        y -= row_h

    # Footer
    c.setFont('Helvetica-Oblique', 7)
    c.drawString(M, 28, 'For clinical use only. Please return completed form to your clinician.')
    c.save()
    buf.seek(0)
    return buf.read()


# ── Item banks ──────────────────────────────────────────────────────────────

SNAP=["Often fails to give close attention to details or makes careless mistakes","Often has difficulty sustaining attention in tasks or play","Often does not seem to listen when spoken to directly","Often does not follow through on instructions and fails to finish work","Often has difficulty organising tasks and activities","Often avoids tasks that require sustained mental effort","Often loses things necessary for tasks or activities","Is often easily distracted by extraneous stimuli","Is often forgetful in daily activities","Often fidgets with hands or feet or squirms in seat","Often leaves seat when remaining seated is expected","Often runs about or climbs in situations where it is inappropriate","Often has difficulty playing or engaging in leisure activities quietly","Is often on the go or acts as if driven by a motor","Often talks excessively","Often blurts out answers before questions are completed","Often has difficulty waiting their turn","Often interrupts or intrudes on others","Often loses temper","Often argues with adults","Often actively defies or refuses adult requests","Often deliberately annoys others","Often blames others for mistakes","Often touchy or easily annoyed","Often angry and resentful","Often spiteful and vindictive"]
VAND_P=["Does not pay attention to details or makes careless mistakes","Has difficulty keeping attention to tasks","Does not seem to listen when spoken to directly","Does not follow through on instructions and fails to finish work","Has difficulty organising tasks and activities","Avoids tasks requiring sustained mental effort","Loses things needed for tasks or activities","Is easily distracted","Is forgetful in daily activities","Fidgets with hands or feet or squirms in seat","Leaves seat when remaining seated is expected","Runs about or climbs too much when staying seated is expected","Has difficulty playing or engaging in quiet activities","Is on the go or driven by a motor","Talks too much","Blurts out answers before questions are finished","Has difficulty waiting in line or for a turn","Interrupts or intrudes on others","Argues with adults","Loses temper","Actively defies or refuses adult requests or rules","Deliberately annoys people","Blames others for mistakes or misbehaviour","Is touchy or easily annoyed by others","Is angry and resentful","Is spiteful","Bullies, threatens or intimidates others","Starts physical fights","Lies to get out of trouble","Truants from school without permission","Breaks rules","Deliberately destroys others' property","Steals things","Performance in reading","Performance in mathematics","Performance in written expression","Relationship with parents","Relationship with siblings","Relationship with peers","Following directions","Disrupting class","Assignment completion","Organisational skills"]
VAND_T=["Fails to give attention to details or makes careless mistakes","Has difficulty keeping attention to tasks or play","Does not seem to listen when spoken to directly","Does not follow through and fails to finish tasks","Has difficulty organising tasks and activities","Avoids tasks requiring sustained mental effort","Loses things necessary for tasks","Is easily distracted","Is forgetful in daily activities","Fidgets with hands or feet or squirms in seat","Leaves seat when remaining seated is expected","Runs about or climbs in situations where it is inappropriate","Has difficulty playing or engaging in leisure activities quietly","Is on the go or driven by a motor","Talks too much","Blurts out answers to questions","Has difficulty waiting in line or turn","Interrupts or intrudes on others","Argues with adults","Loses temper","Actively defies adults' requests","Deliberately annoys people","Blames others for mistakes","Touchy or easily annoyed","Angry and resentful","Spiteful","Reading: quality of work","Reading: completeness","Mathematics: quality of work","Mathematics: completeness","Written expression: quality","Written expression: completeness","Relationship with teachers","Relationship with peers","Following directions","Disrupting class","Completing assignments","Organisational skills"]
SDQ=["Considerate of other people's feelings","Restless, overactive, cannot stay still for long","Often complains of headaches, stomach-aches or sickness","Shares readily with other children","Often has temper tantrums or hot tempers","Rather solitary, tends to play alone","Generally obedient, usually does what adults request","Many worries, often seems worried","Helpful if someone is hurt, upset or feeling ill","Constantly fidgeting or squirming","Has at least one good friend","Often fights with other children or bullies them","Often unhappy, downhearted or tearful","Generally liked by other children","Easily distracted, concentration wanders","Nervous or clingy in new situations, easily loses confidence","Kind to younger children","Often lies or cheats","Picked on or bullied by other children","Often volunteers to help others","Thinks things out before acting","Steals from home, school or elsewhere","Gets along better with adults than with other children","Many fears, easily scared","Sees tasks through to the end, good attention span"]
CQ=["I adjust my language depending on who I am speaking to","I have developed a script to follow in social situations","I monitor my own behaviour when I am around other people","I naturally mimic the behaviour of those around me","I consciously copy the facial expressions of others","I have to consciously work out when to nod or make eye contact","I repeat phrases I have heard other people use","I use strategies to help me appear more natural in social situations","I have practised responses to commonly asked social questions","I act differently in social situations to fit in","I always try to behave in a socially acceptable way","When speaking I think about what my face is doing","I have learned to suppress behaviours that feel natural to me","I am good at fitting in with others","I adjust my body posture depending on who I am talking to","I consciously remind myself of appropriate reactions","I have taught myself to make eye contact during conversations","I feel free to be myself around others","I have to force myself to interact with people","I learn how to interact from watching others","I feel like I am performing rather than being myself","I am good at reading non-verbal cues and body language","I have to force myself to speak with people I don't know","I feel the need to mask my true self","I study people in order to understand how to behave","My inner self is different to what others see","I have developed a persona to present to the world","I can turn on social behaviour when I need to","I socialise differently in groups compared to one-to-one","People tell me I am a good listener","I pick up on social rules by observing others","I have had to learn the rules of conversation","I appear confident even when I am not","I hide my confusion when I do not understand social rules","I find it easier to speak than to listen"]
AQ10A=["I often notice small sounds when others do not","I usually concentrate more on the whole picture, rather than the small details","I find it easy to do more than one thing at once","If there is an interruption, I can switch back to what I was doing very quickly","I find it easy to read between the lines when someone is talking to me","I know how to tell if someone listening to me is getting bored","When reading a story I find it difficult to work out the characters' intentions","I like to collect information about categories of things","I find it easy to work out what someone is thinking or feeling just by looking at their face","I find it difficult to work out people's intentions"]
AQ10C=["S/he often notices small sounds when others do not","S/he usually concentrates more on the whole picture, rather than small details","S/he finds it easy to do more than one thing at once","If there is an interruption, s/he can switch back quickly","S/he finds it easy to read between the lines when someone is talking","S/he knows how to tell if someone listening is getting bored","When reading a story, s/he finds it difficult to work out the characters' intentions","S/he likes to collect information about categories of things","S/he finds it easy to work out what someone is thinking or feeling by looking at them","S/he finds it difficult to work out people's intentions"]
SC=["When I feel frightened, it is hard to breathe","I get headaches when I am at school","I don't like to be with people I don't know well","I get scared if I sleep away from home","I worry about other people liking me","When I get frightened, I feel like passing out","I am nervous","I follow my mother or father wherever they go","People tell me that I look nervous","I feel nervous with people I don't know well","I get stomachaches at school","When I try hard, I feel shaky","I worry about sleeping alone","I worry about being as good as other kids","When I get frightened, I feel like things are not real","I have nightmares about something bad happening to my parents","I worry about going to school","When I get frightened, my heart beats fast","I get shaky","I have nightmares about something bad happening to me","I worry about things working out for me","When I get frightened, I sweat a lot","I am a worrier","I get really frightened for no reason at all","I am afraid to be alone in the house","It is hard for me to talk with people I don't know well","I feel scared when I have to take a test","When I feel frightened, I feel like I am choking","I don't like to be away from my family","I am afraid of having anxiety or panic attacks","I worry that something bad might happen to my parents","I feel shy with people I don't know well","I worry about what is going to happen in the future","When I get frightened, I feel like throwing up","I worry about how well I do things","I am scared to go to school","I worry about things that have already happened","When I get frightened, I feel dizzy","I feel nervous when I am with others and have to do something while they watch me","I feel nervous when going to parties or places with people I don't know","I am shy"]
SP=["When my child feels frightened, it is hard for him/her to breathe","My child gets headaches when at school","My child doesn't like to be with people he/she doesn't know well","My child gets scared if he/she sleeps away from home","My child worries about other people liking him/her","When my child gets frightened, he/she feels like passing out","My child is nervous","My child follows me or my spouse wherever we go","People tell me that my child looks nervous","My child feels nervous with people he/she doesn't know well","My child gets stomachaches at school","When my child tries hard, he/she feels shaky","My child worries about sleeping alone","My child worries about being as good as other kids","When my child gets frightened, he/she feels like things are not real","My child has nightmares about something bad happening to his/her parents","My child worries about going to school","When my child gets frightened, his/her heart beats fast","My child gets shaky","My child has nightmares about something bad happening to him/her","My child worries about things working out","When my child gets frightened, he/she sweats a lot","My child is a worrier","My child gets really frightened for no reason at all","My child is afraid to be alone in the house","It is hard for my child to talk with people he/she doesn't know well","My child feels scared when taking a test","When my child gets frightened, he/she feels like choking","My child doesn't like to be away from his/her family","My child is afraid of having anxiety or panic attacks","My child worries that something bad might happen to his/her parents","My child feels shy with people he/she doesn't know well","My child worries about what is going to happen in the future","When my child gets frightened, he/she feels like throwing up","My child worries about how well he/she does things","My child is scared to go to school","My child worries about things that have already happened","When my child gets frightened, he/she feels dizzy","My child feels nervous when with others and has to do something while they watch","My child feels nervous when going to parties or places with people he/she doesn't know","My child is shy"]
G7=["Feeling nervous, anxious or on edge","Not being able to stop or control worrying","Worrying too much about different things","Trouble relaxing","Being so restless that it is hard to sit still","Becoming easily annoyed or irritable","Feeling afraid as if something awful might happen"]
P9=["Little interest or pleasure in doing things","Feeling down, depressed or hopeless","Trouble falling or staying asleep, or sleeping too much","Feeling tired or having little energy","Poor appetite or overeating","Feeling bad about yourself, or that you are a failure","Trouble concentrating on things","Moving or speaking so slowly others could have noticed, or being fidgety","Thoughts that you would be better off dead or of hurting yourself"]
PA=["Little interest or pleasure in doing things","Feeling down, depressed, or hopeless","Trouble falling asleep, staying asleep, or sleeping too much","Feeling tired or having little energy","Poor appetite, or overeating","Feeling bad about yourself or that you are a failure","Trouble concentrating on things like school work, reading, or watching TV","Moving or speaking so slowly others could have noticed, or being fidgety","Thoughts that you would be better off dead or of hurting yourself","In the past year, have you felt depressed or sad most days, even if you felt okay sometimes?"]
D21=["I found it hard to wind down","I was aware of dryness of my mouth","I couldn't seem to experience any positive feeling at all","I experienced breathing difficulty","I found it difficult to work up the initiative to do things","I tended to over-react to situations","I experienced trembling in the hands","I felt that I was using a lot of nervous energy","I was worried about situations in which I might panic","I felt that I had nothing to look forward to","I found myself getting agitated","I found it difficult to relax","I felt down-hearted and blue","I was intolerant of anything that kept me from getting on","I felt I was close to panic","I was unable to become enthusiastic about anything","I felt I wasn't worth much as a person","I felt that I was rather touchy","I was aware of the action of my heart in the absence of physical exertion","I felt scared without any good reason","I felt that life was meaningless"]
ESS=["Sitting and reading","Watching TV","Sitting inactive in a public place (e.g. theatre or meeting)","As a passenger in a car for an hour without a break","Lying down to rest in the afternoon","Sitting and talking to someone","Sitting quietly after a lunch without alcohol","In a car, while stopped for a few minutes in traffic"]

REGISTRY = {
  ('snap4','parent'):       (SNAP,   ['Not at all','Just a little','Pretty much','Very much'],            'SNAP-IV Rating Scale — Parent Form',        'Rate each item: 0=Not at all  1=Just a little  2=Pretty much  3=Very much'),
  ('snap4','teacher'):      (SNAP,   ['Not at all','Just a little','Pretty much','Very much'],            'SNAP-IV Rating Scale — Teacher Form',       'Rate each item: 0=Not at all  1=Just a little  2=Pretty much  3=Very much'),
  ('vanderbilt','parent'):  (VAND_P, ['Never','Occasionally','Often','Very Often'],                       'Vanderbilt ADHD Assessment — Parent Form',  'Rate frequency: 0=Never  1=Occasionally  2=Often  3=Very Often'),
  ('vanderbilt','teacher'): (VAND_T, ['Never','Occasionally','Often','Very Often'],                       'Vanderbilt ADHD Assessment — Teacher Form', 'Rate frequency: 0=Never  1=Occasionally  2=Often  3=Very Often'),
  ('sdq','parent'):         (SDQ,    ['Not true','Somewhat true','Certainly true'],                       'Strengths & Difficulties — Parent',         'Mark the best description of your child over the last 6 months'),
  ('sdq','teacher'):        (SDQ,    ['Not true','Somewhat true','Certainly true'],                       'Strengths & Difficulties — Teacher',        'Mark the best description of this pupil over the last 6 months'),
  ('sdq','self'):           (SDQ,    ['Not true','Somewhat true','Certainly true'],                       'Strengths & Difficulties — Youth Self',      'Mark what is true for you over the last 6 months'),
  ('catq','self'):          (CQ,     ['1','2','3','4','5','6'],                                          'Camouflaging Autistic Traits (CATq)',        'Rate: 1=Strongly disagree  2  3  4  5  6=Strongly agree'),
  ('aq10','adult'):         (AQ10A,  ['Def. Agree','Slightly Agree','Slightly Disagree','Def. Disagree'], 'Autism Spectrum Quotient — AQ-10 (Adult)',  'Indicate how strongly you agree or disagree with each statement'),
  ('aq10','child'):         (AQ10C,  ['Def. Agree','Slightly Agree','Slightly Disagree','Def. Disagree'], 'Autism Spectrum Quotient — AQ-10 (Child)',  'Indicate how strongly you agree or disagree about your child'),
  ('scared','child'):       (SC,     ['Not true','Somewhat true','Very true'],                            'SCARED — Child Self-Report',                'How often is each true for you? 0=Not true  1=Somewhat true  2=Very true'),
  ('scared','parent'):      (SP,     ['Not true','Somewhat true','Very true'],                            'SCARED — Parent Report',                    'How often is each true for your child? 0=Not true  1=Somewhat true  2=Very true'),
  ('gad7','self'):          (G7,     ['Not at all','Several days','More than half','Nearly every day'],   'GAD-7 Generalised Anxiety Disorder Scale',  'Over the last 2 weeks, how often have you been bothered by:'),
  ('phq9','self'):          (P9,     ['Not at all','Several days','More than half','Nearly every day'],   'PHQ-9 Patient Health Questionnaire',        'Over the last 2 weeks, how often have you been bothered by:'),
  ('phqa','self'):          (PA,     ['Not at all','Several days','More than half','Nearly every day'],   'PHQ-A (Adolescent Depression)',             'Over the last 2 weeks, how often have you been bothered by:'),
  ('dass21','self'):        (D21,    ['0','1','2','3'],                                                   'DASS-21 Depression Anxiety Stress Scales',  'Rate: 0=Did not apply  1=Some degree  2=Considerable degree  3=Very much'),
  ('epworth','self'):       (ESS,    ['0','1','2','3'],                                                   'Epworth Sleepiness Scale',                  'Rate: 0=Never doze  1=Slight chance  2=Moderate chance  3=High chance'),
}

def get_pdf_bytes(sk, rater, client_id=None, client_name=''):
    e = REGISTRY.get((sk, rater))
    if not e:
        return None
    items, labels, title, instr = e
    return _make_pdf(title, client_name, rater, items, labels, instr)
